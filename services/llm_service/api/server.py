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
        return render_messages(roles, merged)

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
            "salutation_prefix": salutation_prefix
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
                base = _base_messages({"user_name": "게스트", "salutation_prefix": ""})
                messages = base + [
                    {"role": "system", "content": "아래 질문에 간결히 답하라. 2~3문장, 280자 이내. 불확실하면 모른다고 답하라."},
                    {"role": "user", "content": user_text},
                ]
                ov = {**(overrides or {})}
                ov.setdefault("enforce_max_sentences", 3)
                ov.setdefault("enforce_max_chars", 280)
                # 옵션: 살짝 더 빠르게
                ov.setdefault("max_new_tokens", 180)
                answer = _ROUTER.generate_messages(messages, overrides=ov)
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

            ctx_msgs = []
            if summary_txt:
                ctx_msgs.append({"role": "system", "content": f"[이전 요약]\n{_clip(summary_txt)}"})
            for m in ctx:
                role = m.get("role", "")
                if role in ("user", "assistant"):
                    ctx_msgs.append({"role": role, "content": _clip(m.get("content", ""))})
            ctx_msgs.append({"role": "system", "content": "아래 질문에 간결히 답하라. 2~3문장, 280자 이내. 불확실하면 모른다고 답하라."})
            ctx_msgs.append({"role": "user", "content": user_text})

            base = _base_messages({
                "user_name": usr_name,
                "salutation_prefix": salutation_prefix
            })
            messages = base + ctx_msgs

            ov = {**(overrides or {})}
            ov.setdefault("enforce_max_sentences", 3)
            ov.setdefault("enforce_max_chars", 280)
            ov.setdefault("max_new_tokens", 180)  # 살짝 더 빠르게
            answer = _ROUTER.generate_messages(messages, overrides=ov)

            # ✅ 항상 호칭 보정
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
                    "salutation_prefix": salutation_prefix
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
