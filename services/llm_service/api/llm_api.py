# services/llm_service/api/llm_api.py
import logging
import re
from flask import request, jsonify

from services.llm_service.model.prompts import render_messages
from services.llm_service.db import llm_repository_cx as repo
from services.llm_service.chains.user_data_chain import build_user_data_chain

log = logging.getLogger("llm_api")


def build_handlers(app, router, cfg):
    """
    cfg와 router를 이용해 최신 로직의 view 함수들을 만들어 dict로 반환.
    (이 함수는 안전하게 언제든 다시 호출 가능)
    """
    # === 설정값들 (JSON 파일에서 로드) ===
    mt = (cfg.get("multiturn") or {})
    CONTEXT_TURNS = int(mt.get("context_turns", 6))
    CTX_CLIP_CHARS = int(mt.get("ctx_clip_chars", 600))
    SUMMARY_TURNS = int(mt.get("summary_turns", 12))

    # 생성 파라미터 (ov_params.json에서)
    generation_cfg = cfg.get("generation", {})
    DEFAULT_MAX_TOKENS = int(generation_cfg.get("max_new_tokens", 180))
    DEFAULT_TEMPERATURE = float(generation_cfg.get("temperature", 0.7))
    DEFAULT_TOP_P = float(generation_cfg.get("top_p", 0.9))
    DEFAULT_TOP_K = int(generation_cfg.get("top_k", 40))

    # 정책 설정 (ov_params.json에서)
    policy_cfg = cfg.get("policy", {})
    MAX_LINES = int(policy_cfg.get("enforce_max_lines", 0))
    FORCE_SUFFIX = policy_cfg.get("force_suffix", "")

    log.info(
        "설정 로드 완료 (랭체인 통합): CONTEXT_TURNS=%d, CTX_CLIP_CHARS=%d, DEFAULT_MAX_TOKENS=%d",
        CONTEXT_TURNS, CTX_CLIP_CHARS, DEFAULT_MAX_TOKENS
    )

    # === 랭체인 초기화 ===
    user_data_chain = build_user_data_chain(router.generate_messages, cfg)
    log.info("사용자 데이터 체인 초기화 완료")

    # ---------- 헬퍼들 ----------
    def get_snippet(key: str, default: str = "") -> str:
        """gguf_prompt.json의 snippets에서 가져오기"""
        return (cfg.get("prompts", {}).get("snippets", {}) or {}).get(key, default)

    def build_base_messages(runtime_vars: dict | None = None):
        """gguf_prompt.json의 roles 기반으로 기본 시스템 메시지 구성"""
        prompts = cfg.get("prompts", {})
        roles = prompts.get("roles", [])
        variables = prompts.get("variables", {})
        merged = {**variables, **(runtime_vars or {})}
        base = render_messages(roles, merged)

        # 사용자 프로필 추가 (gguf_prompt.json의 snippets 사용)
        ua = (merged.get("user_affiliation") or "").strip()
        un = (merged.get("user_name") or "").strip()
        if ua or un:
            profile_text = f"이름: {un or '미상'}\n소속: {ua or '미상'}"
            profile_tmpl = get_snippet("user_profile_header")
            if profile_tmpl:
                base += [{
                    "role": "system",
                    "content": profile_tmpl.replace("{profile_text}", profile_text)
                }]
        return base

    def sanitize_user_text(text: str) -> str:
        """사용자 입력 텍스트 정제"""
        text = (text or "").strip()
        try:
            base_sys = (cfg.get("prompts", {}).get("roles", [])[0].get("content", "")).strip()
        except Exception:
            base_sys = ""
        if base_sys and base_sys in text:
            text = text.replace(base_sys, " ")
        return " ".join(text.split())

    def apply_generation_defaults(overrides: dict) -> dict:
        """ov_params.json의 기본값으로 overrides 보완"""
        ov = dict(overrides)
        ov.setdefault("max_new_tokens", DEFAULT_MAX_TOKENS)
        ov.setdefault("temperature", DEFAULT_TEMPERATURE)
        ov.setdefault("top_p", DEFAULT_TOP_P)
        ov.setdefault("top_k", DEFAULT_TOP_K)
        ov.setdefault("enforce_max_sentences", 3)
        ov.setdefault("enforce_max_chars", 300)
        return ov

    def apply_output_policy(text: str) -> str:
        """ov_params.json의 policy 설정 적용"""
        if not text:
            return text
        if MAX_LINES > 0:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            text = "\n".join(lines[:MAX_LINES])
        if FORCE_SUFFIX:
            lines = text.splitlines() if text else [text]
            lines = [
                ln if ln.endswith(FORCE_SUFFIX) else (ln.rstrip() + " " + FORCE_SUFFIX)
                for ln in lines
            ]
            text = "\n".join(lines).strip()
        return text

    def should_address_user(text: str, overrides: dict) -> bool:
        """사용자 호칭 필요 여부 판단"""
        if overrides.get("force_salutation"):
            return True
        triggers = ["맞을까요", "맞습니까", "확인", "정오", "승인", "괜찮을까요", "고르시겠습니까", "선택하시겠어요"]
        return any(trigger in (text or "") for trigger in triggers)

    def ensure_salutation(prefix: str, text: str) -> str:
        """호칭 접두사 보장"""
        prefix = (prefix or "").strip()
        if not prefix:
            return (text or "").lstrip()
        text = (text or "").lstrip()
        if text.startswith(prefix):
            return text
        return f"{prefix}{text}"

    def extract_affiliation_override(text: str) -> str | None:
        """텍스트에서 대학교명 추출"""
        match = re.search(r'([가-힣A-Za-z]+대학교)', text or "")
        return match.group(1) if match else None

    def is_academic_data_question(user_text: str) -> bool:
        """학업 데이터 관련 질문인지 판단"""
        keywords = [
            # 핵심 지표
            "자료구입", "구입비", "구입 비용", "CPS", "cps",
            "대출", "대출건수", "LPS", "lps",
            "도서관", "방문", "출입", "VPS", "vps",
            "점수", "예측점수", "스코어", "score", "SCR_EST", "scr_est",
            # 학년/연도
            "1학년", "2학년", "3학년", "4학년", "연도", "년도", "언제",
            # 집계/비교
            "총", "전체", "합계", "평균", "비교", "더", "많이", "적게",
            # 행위
            "신청", "예산"
        ]
        return any(keyword in (user_text or "") for keyword in keywords)

    # ---------- 서브 로직 ----------
    def handle_guest_request(user_text: str, first_turn: bool, overrides: dict):
        base = build_base_messages({
            "user_name": "게스트",
            "salutation_prefix": "",
            "user_affiliation": ""
        })
        gk_hint = get_snippet("general_knowledge_hint")
        concise_rule = get_snippet("concise_rule")
        safety_rule = (
            "정확히 알지 못하는 내용은 추측하지 말고 '잘 모르겠습니다'라고 답하라. "
            "특히 전문적이거나 최신 정보가 필요한 질문에는 신중하게 답하라. "
            "현재 질문에만 집중하고 무관한 정보는 언급하지 말라."
        )
        messages = base + []
        if gk_hint:
            messages.append({"role": "system", "content": gk_hint})
        messages.append({"role": "system", "content": safety_rule})
        if concise_rule:
            messages.append({"role": "system", "content": concise_rule})
        messages.append({"role": "user", "content": user_text})

        ov = apply_generation_defaults(overrides)
        body = router.generate_messages(messages, overrides=ov)
        body = apply_output_policy(body)

        final = (
            f"안녕하세요! 저는 Libra 챗봇입니다!\n\n{body}\n\n※ 로그인 시 더 많은 정보와 기능을 활용할 수 있음을 알려드려요!"
            if first_turn else body
        )
        if should_address_user(user_text, ov):
            final = ensure_salutation("", final)
        return final

    def handle_summary_rotation(conv_id: int, usr_name: str, salutation_prefix: str, aff_to_use: str):
        """요약 롤링 처리"""
        summary_rotated = False
        try:
            history_for_rotate = repo.fetch_history(conv_id, limit=SUMMARY_TURNS)
            if len(history_for_rotate) >= SUMMARY_TURNS:
                prev_summary = repo.get_latest_summary(conv_id)
                latest_msg_id = repo.max_msg_id(conv_id)
                conv_dump = "\n".join([f"{m['role']}: {m['content']}" for m in history_for_rotate])

                base = build_base_messages({
                    "user_name": usr_name,
                    "salutation_prefix": salutation_prefix,
                    "user_affiliation": aff_to_use
                })
                sum_messages = base + [
                    {"role": "system", "content": "다음 대화를 5줄 이내 한국어 bullet로 요약하라. 불확실한 내용은 생략."},
                    {"role": "user", "content":
                        f"[기존요약]\n{prev_summary[0] if prev_summary else '(없음)'}\n[대화]\n{conv_dump}"}
                ]
                sum_overrides = {
                    "temperature": 0.2,
                    "max_new_tokens": 160,
                    "enforce_max_sentences": 5,
                    "top_k": DEFAULT_TOP_K,
                    "top_p": DEFAULT_TOP_P
                }
                summary_text = router.generate_messages(sum_messages, overrides=sum_overrides)
                repo.upsert_summary_on_latest_row(
                    conv_id,
                    summary_text=summary_text,
                    cover_to_msg_id=latest_msg_id
                )
                summary_rotated = True
                log.info("요약 롤링 완료: conv_id=%d", conv_id)
        except Exception as e:
            log.warning("요약 롤링 실패: %s", e)
        return summary_rotated

    def handle_auth_request_with_chains(user_text: str, first_turn: bool, overrides: dict, usr_id: str, conv_id: int):
        """랭체인 기반 로그인 사용자 요청 처리"""
        try:
            prof = repo.get_user_profile(usr_id)
        except Exception as e:
            log.exception("DB error(get_user_profile): %s", e)
            raise Exception(f"DB error(get_user_profile): {e}")

        usr_name, usr_snm = prof if prof else ("사용자", "미상")
        salutation_prefix = f"{usr_name}님, "

        # 사용자 메시지 저장
        try:
            repo.append_message(conv_id, usr_id, "user", user_text)
        except Exception as e:
            log.exception("DB error(append user msg): %s", e)
            raise Exception(f"DB error(append user msg): {e}")

        try:
            # 학업 데이터 관련 질문인지 확인
            is_data_question = is_academic_data_question(user_text)

            if is_data_question:
                log.info("학업 데이터 질문 감지 - 랭체인 사용")
                aff_override = extract_affiliation_override(user_text)
                aff_to_use = (aff_override or usr_snm or "")
                chain_input = {
                    "message": user_text,
                    "usr_id": usr_id,
                    "user_name": usr_name,
                    "salutation_prefix": salutation_prefix,
                    "user_affiliation": aff_to_use,
                    "overrides": apply_generation_defaults(overrides)
                }
                result = user_data_chain.invoke(chain_input)
                body = result.get("answer", "답변을 생성할 수 없습니다.")

            else:
                log.info("일반 질문 - 기존 컨텍스트 기반 처리")
                summary_info = repo.get_latest_summary(conv_id)
                _ = (summary_info[0].strip() if summary_info and summary_info[0] else "")

                hist = repo.fetch_history(conv_id, limit=CONTEXT_TURNS + 2)
                if hist and hist[-1].get("role") == "user":
                    hist = hist[:-1]

                gk_hint = get_snippet("general_knowledge_hint")
                concise_rule = get_snippet("concise_rule")
                focus_rule = (
                    "현재 사용자의 질문에만 정확히 답하라. "
                    "이전 대화나 요약 내용이 현재 질문과 관련이 없다면 완전히 무시하라. "
                    "확실하지 않으면 '잘 모르겠습니다'라고 답하라."
                )

                aff_override = extract_affiliation_override(user_text)
                aff_to_use = (aff_override or usr_snm or "")

                base = build_base_messages({
                    "user_name": usr_name,
                    "salutation_prefix": salutation_prefix,
                    "user_affiliation": aff_to_use
                })

                messages = base + []
                if gk_hint:
                    messages.append({"role": "system", "content": gk_hint})
                messages.append({"role": "system", "content": focus_rule})

                if len(hist) > 0:
                    recent_msg = hist[-1]
                    if recent_msg.get("role") in ("user", "assistant"):
                        messages.append({"role": recent_msg["role"], "content": recent_msg.get("content", "")[:300]})

                if concise_rule:
                    messages.append({"role": "system", "content": concise_rule})
                messages.append({"role": "user", "content": user_text})

                ov = apply_generation_defaults(overrides)
                body = router.generate_messages(messages, overrides=ov)

            body = apply_output_policy(body)

            # 로그인 사용자 그리팅 처리
            if first_turn:
                greeting_head = f"안녕하세요! {usr_name}님!"
                answer = f"{greeting_head}\n\n{body}"
            else:
                answer = body

            if should_address_user(user_text, overrides):
                answer = ensure_salutation(salutation_prefix, answer)

        except Exception as e:
            log.exception("LLM error(auth): %s", e)
            raise Exception(f"LLM error: {e}")

        # 어시스턴트 메시지 저장
        try:
            repo.append_message(conv_id, usr_id, "assistant", answer)
        except Exception as e:
            log.exception("DB error(append assistant msg): %s", e)
            raise Exception(f"DB error(append assistant msg): {e}")

        # 요약 롤링 처리
        summary_rotated = handle_summary_rotation(conv_id, usr_name, salutation_prefix, aff_to_use)

        return answer, {
            "used_profile": {"usr_name": usr_name, "usr_snm": usr_snm},
            "summary_rotated": summary_rotated,
            "context_turns": CONTEXT_TURNS,
            "ctx_clip_chars": CTX_CLIP_CHARS,
            "is_data_question": is_data_question
        }

    # ---------- 실제 뷰 함수 ----------
    def health_handler():
        """헬스 체크"""
        return {
            "status": "ok",
            "backend": router.backend_name,
            "model": router.model_name,
            "config": {
                "context_turns": CONTEXT_TURNS,
                "ctx_clip_chars": CTX_CLIP_CHARS,
                "summary_turns": SUMMARY_TURNS,
                "max_tokens": DEFAULT_MAX_TOKENS,
                "temperature": DEFAULT_TEMPERATURE,
                "max_lines": MAX_LINES,
                "langchain_enabled": True
            }
        }

    def generate_handler():
        """메인 대화 생성 엔드포인트 (랭체인 통합)"""
        data = request.get_json(silent=True) or {}
        raw_user_text = (data.get("message") or "").strip()
        overrides = data.get("overrides") or {}

        if not raw_user_text:
            return jsonify({"error": "message is required"}), 400

        user_text = sanitize_user_text(raw_user_text)

        # 첫 턴 판정
        first_turn_flag = (request.headers.get("X-First-Turn", "").strip() == "1")
        usr_id = request.headers.get("X-User-Id")

        log.info("[generate] usr_id=%r, first_turn=%r, msg='%s'", usr_id, first_turn_flag, user_text[:50])

        # ----- 게스트 처리 -----
        if not usr_id:
            try:
                answer = handle_guest_request(user_text, first_turn_flag, overrides)
                return jsonify({"message": user_text, "answer": answer, "guest": True})
            except Exception as e:
                log.exception("게스트 요청 처리 실패: %s", e)
                return jsonify({"error": str(e)}), 500

        # ----- 로그인 사용자 처리 -----
        usr_id = str(usr_id)

        # conv_id 결정
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

        try:
            answer, meta = handle_auth_request_with_chains(user_text, first_turn_flag, overrides, usr_id, conv_id)
            return jsonify({
                "message": user_text,
                "answer": answer,
                "conv_id": conv_id,
                "guest": False,
                "meta": meta
            })
        except Exception as e:
            log.exception("로그인 사용자 요청 처리 실패: %s", e)
            return jsonify({"error": str(e)}), 500

    # 반환: endpoint -> function
    return {
        "health": health_handler,
        "generate": generate_handler,
        "api_generate": generate_handler,
        "api_chat": generate_handler,
    }


def register_routes_once(app, handlers):
    """
    앱 최초 구동 시 한 번만 호출: URL Rule들을 등록
    """
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
    """
    첫 요청 이후에도 허용되는 방식: view function만 갈아끼우기
    (URL Rule은 건드리지 않는다)
    """
    for endpoint, fn in handlers.items():
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = fn
