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
        # 분리 구성 필수: MODEL_PARAMS_CONFIG + MODEL_PROMPTS_CONFIG
        _CFG = load_config(os.environ)
        _ROUTER = ModelRouter.from_config(_CFG, os.environ)

    # ---------- helpers ----------
    def _get_snip(key: str, default: str = "") -> str:
        return (_CFG.get("prompts", {}).get("snippets", {}) or {}).get(key, default)

    def _base_messages(runtime_vars: dict | None = None):
        prompts = _CFG.get("prompts", {})
        roles = prompts.get("roles", [])
        variables = prompts.get("variables", {})
        merged = {**variables, **(runtime_vars or {})}
        base = render_messages(roles, merged)

        # 사용자 프로필(참조용) 시스템 카드: 필요시에만 모델이 활용
        ua = (merged.get("user_affiliation") or "").strip()
        un = (merged.get("user_name") or "").strip()
        if ua or un:
            profile_text = f"이름: {un or '미상'}\n소속: {ua or '미상'}"
            profile_tmpl = _get_snip(
                "user_profile_header",
                "[사용자 프로필]\n{profile_text}\n※ 프로필은 질문과 직접 관련 있을 때만 간단히 활용."
            )
            base += [{
                "role": "system",
                "content": profile_tmpl.replace("{profile_text}", profile_text)
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

    def _affiliation_override_from(text: str) -> str | None:
        """사용자 질문에 '○○대학교'가 있으면 이번 턴만 해당 소속으로 덮어씀."""
        import re
        m = re.search(r'([가-힣A-Za-z]+대학교)', text)
        return m.group(1) if m else None

    def _compose_greeting(is_guest: bool, user_name: str, first_turn: bool) -> tuple[str, str]:
        """
        (head, tail) 반환.
        - 로그인 사용자: 첫 턴이면 "안녕하세요! {이름}님!", tail 없음
        - 게스트: 첫 턴이면 head + tail, 그 외에는 둘 다 공백
        """
        if not first_turn:
            return "", ""
        if is_guest:
            head = _get_snip("greet_guest_prefix", "안녕하세요! 저는 Libra 챗봇입니다!")
            tail = _get_snip("greet_guest_suffix", "로그인 시 더 많은 정보와 기능을 활용할 수 있음을 알려드려요!")
            return head, tail
        else:
            tmpl = _get_snip("greet_member_prefix", "안녕하세요! {usr_name}님!")
            return tmpl.replace("{usr_name}", (user_name or "").strip()), ""

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

    # generate 엔드포인트(별칭 포함)
    @app.route("/generate", methods=["POST"])
    @app.route("/api/generate", methods=["POST"])
    @app.route("/api/chat", methods=["POST"])
    def generate():
        data = request.get_json(silent=True) or {}
        raw_user_text = (data.get("message") or "").strip()
        overrides = data.get("overrides") or {}
        if not raw_user_text:
            return jsonify({"error": "message is required"}), 400

        user_text = _sanitize_user_text(raw_user_text)

        # ⚑ 세션 첫 턴 플래그: 헤더/오버라이드 중 하나라도 True면 True
        first_turn_flag = False
        try:
            if request.headers.get("X-First-Turn", "").strip() == "1":
                first_turn_flag = True
            elif bool(overrides.get("first_turn")):
                first_turn_flag = True
        except Exception:
            pass

        usr_id = request.headers.get("X-User-Id")
        log.info("[generate] X-User-Id=%r, first_turn_flag=%r", usr_id, first_turn_flag)

        gk_hint = _get_snip(
            "general_knowledge_hint",
            "요청 주제가 일반 상식/백과 수준이면, 네가 학습한 일반 지식을 바탕으로 핵심 사실을 요약하라. 불확실하거나 최신 수치가 필요한 부분은 단서를 달아라."
        )
        concise_rule = _get_snip(
            "concise_rule",
            "아래 질문에 간결히 답하라. 2~3문장, 300자 이내. 불확실하면 모른다고 답하라."
        )

        # ----- 게스트 -----
        if not usr_id:
            try:
                base = _base_messages({
                    "user_name": "게스트",
                    "salutation_prefix": "",
                    "user_affiliation": ""
                })
                messages = base + [
                    {"role": "system", "content": gk_hint},
                    {"role": "system", "content": concise_rule},
                    {"role": "user", "content": user_text},
                ]
                ov = {**(overrides or {})}
                ov.setdefault("enforce_max_sentences", 3)
                ov.setdefault("enforce_max_chars", 300)
                ov.setdefault("max_new_tokens", 180)

                body = _ROUTER.generate_messages(messages, overrides=ov)

                # ⚑ 첫 턴이면 인사 앞/뒤를 programmatic으로 붙임
                head, tail = _compose_greeting(is_guest=True, user_name="", first_turn=first_turn_flag)
                final = body
                if head:
                    final = f"{head}\n\n{final}"
                if tail:
                    final = f"{final}\n\n{tail}"

                if _should_address_user(user_text, ov):
                    final = _ensure_salutation("", final)

                return jsonify({"message": user_text, "answer": final, "guest": True})
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

        # conv_id 결정: 헤더 우선 → 없으면 latest or 신규
        try:
            conv_id_hdr = request.headers.get("X-Conv-Id")
            if conv_id_hdr:
                conv_id = int(conv_id_hdr)
            else:
                prev = repo.latest_conv_id(usr_id)
                conv_id = prev if prev is not None else repo.next_conv_id()
        except Exception as e:
            log.exception("DB error(conv): %s", e)
            return jsonify({"error": f"DB error(conv): {e}"}), 500

        # 사용자 메시지 저장
        try:
            repo.append_message(conv_id, usr_id, "user", user_text)
        except Exception as e:
            log.exception("DB error(append user msg): %s", e)
            return jsonify({"error": f"DB error(append user msg): {e}"}), 500

        # 컨텍스트 구성 + 답변 생성
        try:
            summary_info = repo.get_latest_summary(conv_id)
            summary_txt = (summary_info[0].strip() if summary_info and summary_info[0] else "")

            hist = repo.fetch_history(conv_id, limit=CONTEXT_TURNS + 2)
            if hist and hist[-1].get("role") == "user":
                hist = hist[:-1]
            ctx = hist[-CONTEXT_TURNS:] if hist else []

            ctx_msgs = [{"role": "system", "content": gk_hint}]
            if summary_txt:
                ctx_msgs.append({"role": "system", "content": f"[이전 요약]\n{_clip(summary_txt)}"})
            for m in ctx:
                role = m.get("role", "")
                if role in ("user", "assistant"):
                    ctx_msgs.append({"role": role, "content": _clip(m.get("content", ""))})
            ctx_msgs.append({"role": "system", "content": concise_rule})

            # 질문 내 명시 소속(예: 서울대학교)이 있으면 이번 턴만 덮어쓰기
            aff_override = _affiliation_override_from(user_text)
            aff_to_use = (aff_override or usr_snm or "")
            base = _base_messages({
                "user_name": usr_name,
                "salutation_prefix": salutation_prefix,
                "user_affiliation": aff_to_use
            })
            ctx_msgs.append({"role": "user", "content": user_text})

            messages = base + ctx_msgs

            ov = {**(overrides or {})}
            ov.setdefault("enforce_max_sentences", 3)
            ov.setdefault("enforce_max_chars", 300)
            ov.setdefault("max_new_tokens", 180)

            body = _ROUTER.generate_messages(messages, overrides=ov)

            # ⚑ 첫 턴이면 로그인 인사(head)만 앞에 붙임
            head, tail = _compose_greeting(is_guest=False, user_name=usr_name, first_turn=first_turn_flag)
            answer = body
            if head:
                answer = f"{head}\n\n{body}"
            # 로그인 사용자는 tail 없음

            if _should_address_user(user_text, ov):
                answer = _ensure_salutation(salutation_prefix, answer)

        except Exception as e:
            log.exception("LLM error(auth): %s", e)
            return jsonify({"error": f"LLM error: {e}"}), 500

        # 어시스턴트 메시지 저장
        try:
            repo.append_message(conv_id, usr_id, "assistant", answer)
        except Exception as e:
            log.exception("DB error(append assistant msg): %s", e)
            return jsonify({"error": f"DB error(append assistant msg): {e}"}), 500

        # (요약 롤링은 필요 시 기존 로직 사용 가능. 여기서는 생략/유지 선택)
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
                    "user_affiliation": aff_to_use
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
