# services/llm_service/api/server.py
import os
import pathlib
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# LLM 라우터/컨피그
from services.llm_service.model.router import ModelRouter
from services.llm_service.model.config_loader import load_config

# Oracle(cx_Oracle) DAO
from services.llm_service.db import llm_repository_cx as repo

_ROUTER = None
log = logging.getLogger("llm_api")
logging.basicConfig(
    level=getattr(logging, os.getenv("APP_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

def create_app():
    app = Flask(__name__)

    # === .env 로드 ===
    env_path = pathlib.Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))

    # (선택) Windows Instant Client PATH 보강 (Thick 모드 사용할 때만 의미)
    ic_path = (os.getenv("ORACLE_CLIENT_PATH") or "").strip()
    if ic_path and ic_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ic_path + os.pathsep + os.environ.get("PATH", "")

    # === 멀티턴 컨텍스트/요약 설정 ===
    CONTEXT_TURNS   = int(os.getenv("CONTEXT_TURNS", "8"))     # 프롬프트에 포함할 최근 턴 수
    CTX_CLIP_CHARS  = int(os.getenv("CTX_CLIP_CHARS", "900"))  # 각 메시지 최대 길이(문자)
    SUMMARY_TURNS   = int(os.getenv("SUMMARY_TURNS", "12"))    # 요약 트리거 기준(턴 수)

    # === LLM 컨피그 로드 + 라우터 준비 ===
    global _ROUTER
    if _ROUTER is None:
        cfg_path = os.getenv("MODEL_CONFIG")
        if not cfg_path:
            raise RuntimeError("MODEL_CONFIG is not set in .env (e.g. services/llm_service/model/configs/gguf.json)")
        cfg = load_config(cfg_path, os.environ)
        _ROUTER = ModelRouter.from_config(cfg, os.environ)

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

    @app.post("/generate")
    def generate():
        """
        Body:
        {
          "message": "질문",
          "overrides": { "temperature": 0.5, "max_new_tokens": 256 }  # (옵션)
        }
        Header:
          X-User-Id: <USR_ID>  # 로그인 시에만
        """
        data = request.get_json(silent=True) or {}
        user_text = (data.get("message") or "").strip()
        overrides = data.get("overrides") or {}
        if not user_text:
            return jsonify({"error": "message is required"}), 400

        # 1) 로그인 여부 식별: 헤더 우선
        usr_id = request.headers.get("X-User-Id")
        log.info("[generate] X-User-Id=%r", usr_id)

        # ===== 게스트 모드 =====
        if not usr_id:
            guide = "로그인 시 대화가 저장되어 멀티턴이 가능합니다."
            try:
                answer = _ROUTER.generate(
                    user_text=f"[게스트]\n{user_text}\n\n(안내: {guide})",
                    overrides=overrides
                )
                return jsonify({"message": user_text, "answer": answer, "guest": True})
            except Exception as e:
                log.exception("LLM error(guest): %s", e)
                return jsonify({"error": str(e)}), 500

        # ===== 로그인 모드 =====
        usr_id = str(usr_id)

        # (a) 프로필 조회 (USER_DATA.USR_NAME, USR_SNM)
        try:
            prof = repo.get_user_profile(usr_id)  # -> (usr_name, usr_snm) or None
        except Exception as e:
            log.exception("DB error(get_user_profile): %s", e)
            return jsonify({"error": f"DB error(get_user_profile): {e}"}), 500

        usr_name, usr_snm = prof if prof else ("사용자", "미상")
        preface = f"[사용자: {usr_name} / 소속: {usr_snm}]"

        # (b) 대화방 결정(최근 conv 재사용, 없으면 신규)
        try:
            conv_id = repo.latest_conv_id(usr_id)
            if conv_id is None:
                conv_id = repo.next_conv_id()
        except Exception as e:
            log.exception("DB error(conv): %s", e)
            return jsonify({"error": f"DB error(conv): {e}"}), 500

        # (c) 사용자 메시지 저장 (먼저 저장해 로깅/감사 확보)
        try:
            repo.append_message(conv_id, usr_id, "user", user_text)
        except Exception as e:
            log.exception("DB error(append user msg): %s", e)
            return jsonify({"error": f"DB error(append user msg): {e}"}), 500

        # (d) 컨텍스트 조립: 요약 + 최근 N턴(방금 저장한 user는 중복 방지로 제외)
        try:
            # 요약(있으면) 가져오기
            summary_info = repo.get_latest_summary(conv_id)  # -> (text, covered_msg_id) | None
            summary_txt = (summary_info[0].strip() if summary_info and summary_info[0] else "")

            # 최근 히스토리 가져오기(조금 넉넉히)
            hist = repo.fetch_history(conv_id, limit=CONTEXT_TURNS + 2)
            # 끝 요소가 방금 저장한 user면 중복 방지로 제외
            if hist and hist[-1].get("role") == "user":
                hist = hist[:-1]
            # 오래된 → 최신 순으로 이미 정렬되어 있다고 가정, 뒤쪽 N턴만 사용
            ctx = hist[-CONTEXT_TURNS:] if hist else []

            def _clip(s: str) -> str:
                s = (s or "").strip()
                return (s[:CTX_CLIP_CHARS] + "…") if len(s) > CTX_CLIP_CHARS else s

            parts = [preface]

            if summary_txt:
                parts.append("[대화 요약]\n" + _clip(summary_txt))

            if ctx:
                parts.append("[최근 대화]")
                for m in ctx:
                    role = m.get("role", "")
                    role_ko = "사용자" if role == "user" else ("어시스턴트" if role == "assistant" else role)
                    parts.append(f"{role_ko}: {_clip(m.get('content',''))}")

            # 현재 질문은 별도 섹션으로 뒤에
            parts.append("[현재 질문]\n" + user_text)
            parts.append("위 맥락을 기억해서, 한국어로 최대 2줄로 간결히 답해줘.")

            final_prompt = "\n\n".join(parts)

            #  (e) LLM 호출
            answer = _ROUTER.generate(
                user_text=final_prompt,
                overrides=overrides
            )
        except Exception as e:
            log.exception("LLM error(auth): %s", e)
            return jsonify({"error": f"LLM error: {e}"}), 500

        # (f) 어시스턴트 메시지 저장
        try:
            repo.append_message(conv_id, usr_id, "assistant", answer)
        except Exception as e:
            log.exception("DB error(append assistant msg): %s", e)
            return jsonify({"error": f"DB error(append assistant msg): {e}"}), 500

        # (g) 롤링 요약 (요약 기준: SUMMARY_TURNS)
        summary_rotated = False
        try:
            history_for_rotate = repo.fetch_history(conv_id, limit=SUMMARY_TURNS)
            if len(history_for_rotate) >= SUMMARY_TURNS:
                prev_summary = repo.get_latest_summary(conv_id)  # (text, covered_id) | None
                latest_msg_id = repo.max_msg_id(conv_id)

                conv_dump = "\n".join([f"{m['role']}: {m['content']}" for m in history_for_rotate])
                summarize_prompt = f"""아래 대화를 5줄 내 핵심만 요약해줘.
[기존요약]
{prev_summary[0] if prev_summary else '(없음)'}
[대화]
{conv_dump}
"""
                summary_text = _ROUTER.generate(
                    user_text=summarize_prompt,
                    overrides={"temperature": 0.2, "max_new_tokens": 256}
                )
                repo.upsert_summary_on_latest_row(
                    conv_id,
                    summary_text=summary_text,
                    cover_to_msg_id=latest_msg_id
                )
                summary_rotated = True
        except Exception as e:
            # 요약 실패는 치명적이지 않으므로 경고만
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
    # 리로더 중복 로딩 방지 및 멀티스레드
    app.run(host="0.0.0.0", port=5150, debug=False, use_reloader=False, threaded=True)
