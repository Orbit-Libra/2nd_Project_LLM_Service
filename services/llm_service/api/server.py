# services/llm_service/api/server.py
import os
import pathlib
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from services.llm_service.model.router import ModelRouter
from services.llm_service.model.config_loader import load_config
from services.llm_service.model.prompts import render_messages
from services.llm_service.db import llm_repository_cx as repo

_ROUTER = None
_CFG = None
log = logging.getLogger("llm_api")
logging.basicConfig(
    level=getattr(logging, os.getenv("APP_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

def create_app():
    app = Flask(__name__)

    # === .env ===
    env_path = pathlib.Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))

    # (선택) Oracle Client PATH
    ic_path = (os.getenv("ORACLE_CLIENT_PATH") or "").strip()
    if ic_path and ic_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ic_path + os.pathsep + os.environ.get("PATH", "")

    # === 멀티턴 설정 ===
    CONTEXT_TURNS   = int(os.getenv("CONTEXT_TURNS", "8"))
    CTX_CLIP_CHARS  = int(os.getenv("CTX_CLIP_CHARS", "900"))
    SUMMARY_TURNS   = int(os.getenv("SUMMARY_TURNS", "12"))

    # === 라우터 준비 ===
    global _ROUTER, _CFG
    if _ROUTER is None:
        cfg_path = os.getenv("MODEL_CONFIG")
        if not cfg_path:
            raise RuntimeError("MODEL_CONFIG is not set in .env")
        _CFG = load_config(cfg_path, os.environ)
        _ROUTER = ModelRouter.from_config(_CFG, os.environ)

    # ---------- helpers ----------
    def _base_messages(runtime_vars: dict | None = None):
        prompts = _CFG.get("prompts", {})
        roles = prompts.get("roles", [])
        variables = prompts.get("variables", {})
        merged = {**variables, **(runtime_vars or {})}
        base = render_messages(roles, merged)

        # 사용자 프로필(참조용) 시스템 카드 추가: 필요할 때만 모델이 활용
        ua = (merged.get("user_affiliation") or "").strip()
        un = (merged.get("user_name") or "").strip()
        if ua or un:
            base += [{
                "role": "system",
                "content": (
                    "[사용자 프로필]\n"
                    f"이름: {un or '미상'}\n"
                    f"소속: {ua or '미상'}\n"
                    "※ 프로필은 질문과 직접 관련 있을 때만 간단히 활용."
                )
            }]
        return base

    def _sanitize_user_text(t: str) -> str:
        t = (t or "").strip()
        try:
            base_sys = (_CFG.get("prompts", {}).get("roles", [])[0].get("content", "")).strip()
        except Exception:
            base_sys = ""
        if base_sys and base_sys in t:
            t = t.replace(base_sys, " ")
        return " ".join(t.split())

    def _clip(s: str) -> str:
        s = (s or "").strip()
        return (s[:CTX_CLIP_CHARS] + "…") if len(s) > CTX_CLIP_CHARS else s

    def _ensure_salutation(prefix: str, text: str) -> str:
        """prefix가 있으면 답변을 반드시 해당 호칭으로 시작하게 보정"""
        prefix = (prefix or "").strip()
        if not prefix:
            return (text or "").lstrip()
        t = (text or "").lstrip()
        # 이미 붙어 있으면 중복 방지
        if t.startswith(prefix):
            return t
        return f"{prefix}{t[0].lower() if t[:2].startswith(', ') else ''}{t}"

    def _should_address_user(text: str, overrides: dict) -> bool:
        """
        이름/호칭을 붙일지 조건부 판단:
        - 프론트에서 force_salutation을 명시하면 항상 적용
        - 확인/정오/승인/선택 등 사용자 결정을 유도하는 표현이 있을 때만 자동 적용
        """
        if overrides.get("force_salutation"):
            return True
        triggers = ["맞을까요", "맞습니까", "확인", "정오", "승인", "괜찮을까요", "고르시겠습니까", "선택하시겠어요"]
        t = (text or "")
        return any(k in t for k in triggers)

    # ---------- endpoints ----------
    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "backend": _ROUTER.backend_name,
            "model": _ROUTER.model_name,
            "context_turns": CONTEXT_TURNS,
            "ctx_clip_chars": CTX_CLIP_CHARS,
            "summary_turns": SUMMARY_TURNS,
        }

    @app.get("/greet")
    def greet():
        usr_id = request.headers.get("X-User-Id")
        log.info("[greet] X-User-Id=%r", usr_id)

        usr_name, usr_snm = ("게스트", "")
        salutation_prefix = ""
        is_guest = True

        if usr_id:
            try:
                prof = repo.get_user_profile(str(usr_id))
                if prof:
                    usr_name, usr_snm = prof
                    salutation_prefix = f"{usr_name}님, "
                    is_guest = False
            except Exception as e:
                log.exception("DB error(get_user_profile in greet): %s", e)

        base = _base_messages({
            "user_name": usr_name,
            "salutation_prefix": salutation_prefix,
            "user_affiliation": usr_snm or ""
        })

        messages = base + [
            {"role": "system",
             "content": (
                 "페이지 첫 인사를 1~2문장으로 작성하라. "
                 "게스트면 자기소개(예: Libra 챗봇)와 도움 가능한 범주를 간단히 말하고, "
                 "로그인 사용자는 '{salutation_prefix}'로 시작하라(비어있으면 생략). "
                 "과장/허위 약속 금지, 친근하되 공손하게."
             )},
            {"role": "user", "content": "[초기 인사 요청]"}
        ]

        ov = {"temperature": 0.6, "enforce_max_sentences": 2, "enforce_max_chars": 140}
        try:
            greeting = _ROUTER.generate_messages(messages, overrides=ov)
            # 안전 보정
            greeting = _ensure_salutation(salutation_prefix, greeting)
            return jsonify({
                "greeting": greeting,
                "guest": is_guest,
                "used_profile": None if is_guest else {"usr_name": usr_name, "usr_snm": usr_snm}
            })
        except Exception as e:
            log.exception("LLM error(greet): %s", e)
        fallback = "안녕하세요! Libra 챗봇입니다. 무엇을 도와드릴까요?" if is_guest else f"{usr_name}님, 무엇을 도와드릴까요?"
        return jsonify({"greeting": fallback, "guest": is_guest}), 200

    @app.post("/generate")
    def generate():
        data = request.get_json(silent=True) or {}
        raw_user_text = (data.get("message") or "").strip()
        overrides = data.get("overrides") or {}
        if not raw_user_text:
            return jsonify({"error": "message is required"}), 400

        user_text = _sanitize_user_text(raw_user_text)

        usr_id = request.headers.get("X-User-Id")
        log.info("[generate] X-User-Id=%r", usr_id)

        # ----- 게스트 -----
        if not usr_id:
            try:
                base = _base_messages({
                    "user_name": "게스트",
                    "salutation_prefix": "",
                    "user_affiliation": ""
                })
                messages = base + [
                    {"role": "system", "content": "요청 주제가 일반 상식/백과 수준이면, 학습한 일반 지식을 바탕으로 핵심 사실을 요약하라. 불확실하거나 최신 수치가 필요한 부분은 단서를 달아라."},
                    {"role": "system", "content": "아래 질문에 간결히 답하라. 2~3문장, 300자 이내. 불확실하면 모른다고 답하라."},
                    {"role": "user", "content": user_text},
                ]
                ov = {**(overrides or {})}
                ov.setdefault("enforce_max_sentences", 3)
                ov.setdefault("enforce_max_chars", 300)  # 소속/맥락 보강 여유
                ov.setdefault("max_new_tokens", 180)
                answer = _ROUTER.generate_messages(messages, overrides=ov)
                # 필요할 때만 이름/호칭 사용 (게스트는 기본 비활성)
                if _should_address_user(user_text, ov):
                    answer = _ensure_salutation("", answer)
                return jsonify({"message": user_text, "answer": answer, "guest": True})
            except Exception as e:
                log.exception("LLM error(guest): %s", e)
                return jsonify({"error": str(e)}), 500

        # ----- 로그인 -----
        usr_id = str(usr_id)

        try:
            prof = repo.get_user_profile(usr_id)
        except Exception as e:
            log.exception("DB error(get_user_profile): %s", e)
            return jsonify({"error": f"DB error(get_user_profile): {e}"}), 500

        usr_name, usr_snm = prof if prof else ("사용자", "미상")
        salutation_prefix = f"{usr_name}님, "

        try:
            conv_id = repo.latest_conv_id(usr_id)
            if conv_id is None:
                conv_id = repo.next_conv_id()
        except Exception as e:
            log.exception("DB error(conv): %s", e)
            return jsonify({"error": f"DB error(conv): {e}"}), 500

        try:
            repo.append_message(conv_id, usr_id, "user", user_text)
        except Exception as e:
            log.exception("DB error(append user msg): %s", e)
            return jsonify({"error": f"DB error(append user msg): {e}"}), 500

        try:
            summary_info = repo.get_latest_summary(conv_id)
            summary_txt = (summary_info[0].strip() if summary_info and summary_info[0] else "")

            hist = repo.fetch_history(conv_id, limit=CONTEXT_TURNS + 2)
            if hist and hist[-1].get("role") == "user":
                hist = hist[:-1]
            ctx = hist[-CONTEXT_TURNS:] if hist else []

            # 일반 상식은 답하도록 힌트를 컨텍스트 맨 앞에 둔다
            general_knowledge_hint = {
                "role": "system",
                "content": (
                    "요청 주제가 일반 상식/백과 수준이면, 네가 학습한 일반 지식을 바탕으로 핵심 사실을 요약하라. "
                    "불확실하거나 최신 수치가 필요한 부분은 단서를 달아라."
                )
            }

            ctx_msgs = [general_knowledge_hint]
            if summary_txt:
                ctx_msgs.append({"role": "system", "content": f"[이전 요약]\n{_clip(summary_txt)}"})
            for m in ctx:
                role = m.get("role", "")
                if role in ("user", "assistant"):
                    ctx_msgs.append({"role": role, "content": _clip(m.get("content", ""))})
            ctx_msgs.append({"role": "system", "content": "아래 질문에 간결히 답하라. 2~3문장, 300자 이내. 불확실하면 모른다고 답하라."})
            ctx_msgs.append({"role": "user", "content": user_text})

            base = _base_messages({
                "user_name": usr_name,
                "salutation_prefix": salutation_prefix,
                "user_affiliation": usr_snm or ""
            })
            messages = base + ctx_msgs

            ov = {**(overrides or {})}
            ov.setdefault("enforce_max_sentences", 3)
            ov.setdefault("enforce_max_chars", 300)  # 소속/맥락 보강 여유
            ov.setdefault("max_new_tokens", 180)  # 살짝 더 빠르게
            answer = _ROUTER.generate_messages(messages, overrides=ov)

            # 필요할 때만 이름/호칭 사용 (확인/승인 류)
            if _should_address_user(user_text, ov):
                answer = _ensure_salutation(salutation_prefix, answer)

        except Exception as e:
            log.exception("LLM error(auth): %s", e)
            return jsonify({"error": f"LLM error: {e}"}), 500

        try:
            repo.append_message(conv_id, usr_id, "assistant", answer)
        except Exception as e:
            log.exception("DB error(append assistant msg): %s", e)
            return jsonify({"error": f"DB error(append assistant msg): {e}"}), 500

        # 요약 롤링
        summary_rotated = False
        try:
            history_for_rotate = repo.fetch_history(conv_id, limit=SUMMARY_TURNS)
            if len(history_for_rotate) >= SUMMARY_TURNS:
                prev_summary = repo.get_latest_summary(conv_id)
                latest_msg_id = repo.max_msg_id(conv_id)
                conv_dump = "\n".join([f"{m['role']}: {m['content']}" for m in history_for_rotate])

                base = _base_messages({
                    "user_name": usr_name,
                    "salutation_prefix": salutation_prefix,
                    "user_affiliation": usr_snm or ""
                })
                sum_messages = base + [
                    {"role": "system", "content": "다음 대화를 5줄 이내 한국어 bullet로 요약하라. 불확실한 내용은 생략."},
                    {"role": "user", "content": f"[기존요약]\n{prev_summary[0] if prev_summary else '(없음)'}\n[대화]\n{conv_dump}"}
                ]
                sum_overrides = {"temperature": 0.2, "max_new_tokens": 160, "enforce_max_sentences": 5}
                summary_text = _ROUTER.generate_messages(sum_messages, overrides=sum_overrides)
                repo.upsert_summary_on_latest_row(conv_id, summary_text=summary_text, cover_to_msg_id=latest_msg_id)
                summary_rotated = True
        except Exception as e:
            log.warning("summary rotate skipped: %s", e)

        return jsonify({
            "message": user_text,
            "answer": answer,
            "conv_id": conv_id,
            "guest": False,
            "meta": {
                "used_profile": {"usr_name": usr_name, "usr_snm": usr_snm},
                "summary_rotated": summary_rotated,
                "context_turns": CONTEXT_TURNS,
                "ctx_clip_chars": CTX_CLIP_CHARS,
            }
        })

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5150, debug=False, use_reloader=False, threaded=True)
