# services/llm_service/api/llm_api.py
import os, logging
from flask import request, jsonify
from services.llm_service.db import llm_repository_cx as repo
from services.llm_service.orchestrator import handle as orchestrate
from services.llm_service.orchestrator.schemas import OrchestratorInput

log = logging.getLogger("llm_api")

def build_handlers(app, router, cfg):
    mt = (cfg.get("multiturn") or {})
    CONTEXT_TURNS = int(mt.get("context_turns", 6))
    SUMMARY_TURNS = int(mt.get("summary_turns", 12))

    def apply_output_policy(text: str) -> str:
        pol = cfg.get("policy", {})
        if not text: return text
        max_lines = int(pol.get("enforce_max_lines", 0))
        if max_lines > 0:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            text = "\n".join(lines[:max_lines])
        suffix = pol.get("force_suffix", "")
        if suffix:
            lines = text.splitlines() if text else [text]
            lines = [ln if ln.endswith(suffix) else (ln.rstrip() + " " + suffix) for ln in lines]
            text = "\n".join(lines).strip()
        return text

    def handle_summary_rotation(conv_id: int):
        # 기존의 요약 롤링 로직을 간략히 유지
        try:
            history_for_rotate = repo.fetch_history(conv_id, limit=SUMMARY_TURNS)
            if len(history_for_rotate) >= SUMMARY_TURNS:
                prev_summary = repo.get_latest_summary(conv_id)
                latest_msg_id = repo.max_msg_id(conv_id)
                conv_dump = "\n".join([f"{m['role']}: {m['content']}" for m in history_for_rotate])

                sum_messages = [
                    {"role": "system", "content": "다음 대화를 5줄 이내 한국어 bullet로 요약하라. 불확실한 내용은 생략."},
                    {"role": "user", "content": f"[기존요약]\n{prev_summary[0] if prev_summary else '(없음)'}\n[대화]\n{conv_dump}"}
                ]
                summary_text = router.generate_messages(sum_messages, overrides={
                    "temperature": 0.2, "max_new_tokens": 160, "enforce_max_sentences": 5
                })
                repo.upsert_summary_on_latest_row(conv_id, summary_text=summary_text, cover_to_msg_id=latest_msg_id)
                return True
        except Exception as e:
            log.warning("요약 롤링 실패: %s", e)
        return False

    def health_handler():
        return {
            "status": "ok",
            "backend": router.backend_name,
            "model": router.model_name,
            "config": {
                "context_turns": CONTEXT_TURNS,
                "summary_turns": SUMMARY_TURNS,
                "langchain_enabled": True
            }
        }

    def generate_handler():
        data = request.get_json(silent=True) or {}
        user_text = (data.get("message") or "").strip()
        overrides = data.get("overrides") or {}
        if not user_text:
            return jsonify({"error": "message is required"}), 400

        first_turn_flag = (request.headers.get("X-First-Turn", "").strip() == "1")
        usr_id = request.headers.get("X-User-Id")
        usr_id = str(usr_id) if usr_id else None

        # conv_id 결정
        if usr_id:
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
        else:
            conv_id = None

        # 사용자 메시지 저장 (로그인 사용자만)
        if usr_id and conv_id is not None:
            try:
                repo.append_message(conv_id, usr_id, "user", user_text)
            except Exception as e:
                log.exception("DB error(append user msg): %s", e)
                return jsonify({"error": f"DB error: {e}"}), 500

        # ==== 오케스트레이터 호출 ====
        log.info(
            "[SESSION] usr_id=%r conv_id=%r first_turn=%r",
            usr_id, conv_id, first_turn_flag
        )
        inp = OrchestratorInput(
            query=user_text,
            usr_id=usr_id,
            conv_id=conv_id,
            first_turn=first_turn_flag,
            overrides=overrides,
            headers=dict(request.headers),
            meta={"client": "web", "locale": "ko-KR", "session": {}}
        )
        try:
            out = orchestrate(router, cfg, repo, inp)
            answer = out.answer
            route = out.route
            meta = out.meta or {}
            intent = (meta.get("intent") or {})
            log.info(
                "[ROUTE] kind=%s reason=%s via=%s agent=%s slots=%s calc=%s external=%s",
                intent.get("kind"), intent.get("reason"), route,
                ("enabled" if os.getenv("AGENT_ENABLED","false").lower()=="true" else "disabled"),
                len((intent.get("user_slots") or [])),
                intent.get("wants_calculation"),
                intent.get("external_entities"),
            )
            
        except Exception as e:
            log.exception("오케스트레이터 처리 실패: %s", e)
            return jsonify({"error": str(e)}), 500
        

        # UX: 첫 턴 그리팅(게스트/로그인)
        if first_turn_flag:
            if usr_id:
                try:
                    prof = repo.get_user_profile(usr_id)
                    usr_name = (prof[0] if prof else "사용자")
                except Exception:
                    usr_name = "사용자"
                answer = f"안녕하세요! {usr_name}님!\n\n{answer}"
            else:
                answer = f"안녕하세요! 저는 Libra 챗봇입니다!\n\n{answer}\n\n※ 로그인 시 더 많은 정보와 기능을 활용할 수 있음을 알려드려요!"

        answer = apply_output_policy(answer)

        # 어시스턴트 메시지 저장 + 요약 롤링 (로그인 사용자만)
        if usr_id and conv_id is not None:
            try:
                repo.append_message(conv_id, usr_id, "assistant", answer)
            except Exception as e:
                log.exception("DB error(append assistant msg): %s", e)
            _ = handle_summary_rotation(conv_id)

        return jsonify({
            "message": user_text,
            "answer": answer,
            "conv_id": conv_id,
            "guest": not bool(usr_id),
            "meta": {"route": route, **(meta or {})}
        })

    return {
        "health": health_handler,
        "generate": generate_handler,
        "api_generate": generate_handler,
        "api_chat": generate_handler,
    }

def register_routes_once(app, handlers):
    mapping = [
        ("/health", "health", ["GET"]),
        ("/generate", "generate", ["POST"]),
        ("/api/generate", "api_generate", ["POST"]),
        ("/api/chat", "api_chat", ["POST"]),
    ]
    for rule, endpoint, methods in mapping:
        if endpoint not in app.view_functions:
            app.add_url_rule(rule, endpoint, handlers[endpoint], methods=methods)

def rebind_handlers(app, handlers):
    for endpoint, fn in handlers.items():
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = fn
