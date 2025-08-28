import logging
import os
import re
from typing import List, Optional

from .schemas import OrchestratorInput, OrchestratorOutput
from . import intent_classifier, local_exec, planner, agent_client  # 사용됨 (Pylance OK)

log = logging.getLogger("orchestrator")
ilog = logging.getLogger("orchestrator.intent")

AGENT_ENABLED = os.getenv("AGENT_ENABLED", "false").lower() == "true"


# =========================
# RAG 합성 유틸
# =========================
def _format_rag_snippets(matches, max_chars=1400, max_items=5) -> str:
    """에이전트가 준 RAG 매치들을 시스템 컨텍스트로 정리"""
    items = (matches or [])[:max_items]
    lines = ["[USAGE GUIDE SNIPPETS]"]
    used = 0
    for i, m in enumerate(items, 1):
        if isinstance(m, str):
            txt, meta, score = m.strip(), {}, None
        else:
            txt = (m.get("text") or "").strip()
            meta = m.get("meta") or {}
            score = m.get("score")
        if not txt:
            continue
        page = meta.get("page")
        head = f"- #{i} (p.{page})" if page else f"- #{i}"
        chunk = f"{head} {txt}"
        if used + len(chunk) > max_chars:
            break
        lines.append(chunk)
        used += len(chunk)
    return "\n".join(lines)


def _synthesize_from_rag(router, cfg, query: str, rag: dict, overrides: dict, usr_name="게스트", usr_snm=""):
    """RAG 스니펫 + 시스템 규칙으로 최종 답변 합성 (개선된 프롬프트)"""
    base = local_exec.build_base_messages(cfg, {
        "user_name": usr_name,
        "salutation_prefix": "",
        "user_affiliation": usr_snm or ""
    })
    concise_rule = ((cfg.get("prompts", {}).get("snippets", {}) or {}).get("concise_rule") or "")
    
    # 개선된 합성 규칙 - 더 자연스럽고 도움되는 답변 유도
    sys_rule = (
        "아래 제공된 문서 스니펫을 바탕으로 사용자의 질문에 친절하고 구체적으로 답하라. "
        "스니펫의 정보를 종합하여 단계별 안내나 구체적인 방법을 제시하라. "
        "스니펫에 부분적 정보만 있다면, 있는 정보를 최대한 활용하여 도움이 되는 답변을 만들어라. "
        "완전히 관련 없는 내용이 아닌 이상 적극적으로 안내하라."
    )
    
    snippets = _format_rag_snippets((rag or {}).get("matches") or [])

    messages = list(base)
    messages.append({"role": "system", "content": sys_rule})
    if snippets:
        messages.append({"role": "system", "content": snippets})
    
    # 질문별 맞춤 가이드 추가
    query_lower = query.lower()
    if any(keyword in query_lower for keyword in ["회원가입", "가입", "계정생성"]):
        guide = (
            "회원가입에 대한 질문입니다. 가입 절차, 필요한 정보, 접근 경로 등을 "
            "순서대로 친절하게 설명해주세요. 구체적인 버튼명이나 페이지명이 있다면 명시하세요."
        )
        messages.append({"role": "system", "content": guide})
    elif any(keyword in query_lower for keyword in ["개인정보", "정보수정", "프로필"]):
        guide = (
            "개인정보 관리에 대한 질문입니다. 정보 수정 방법, 접근 경로, 필요한 단계를 "
            "구체적으로 안내해주세요. 관련 메뉴나 버튼 위치도 포함하세요."
        )
        messages.append({"role": "system", "content": guide})
    elif any(keyword in query_lower for keyword in ["로그인", "인증"]):
        guide = (
            "로그인/인증에 대한 질문입니다. 로그인 방법, 문제 해결 방법, 관련 기능을 "
            "단계별로 친절하게 설명해주세요."
        )
        messages.append({"role": "system", "content": guide})
    
    if concise_rule:
        messages.append({"role": "system", "content": concise_rule})
    messages.append({"role": "user", "content": query})

    # 생성 파라미터 조정 - 더 풍부한 답변을 위해
    ov = local_exec.apply_generation_defaults(cfg, overrides or {})
    ov["max_new_tokens"] = max(ov.get("max_new_tokens", 180), 250)  # 최소 250토큰 보장
    ov["temperature"] = max(ov.get("temperature", 0.7), 0.5)  # 약간의 창의성 허용
    
    body = router.generate_messages(messages, overrides=ov)
    return local_exec.apply_output_policy(cfg, body)


def _extract_rag_blob(res: dict) -> Optional[dict]:
    """
    에이전트 응답에서 RAG 결과를 최대한 관대하게 찾는다.
    지원 형태:
      - top-level: {"rag": {...}}, {"context_snippets": [...]}, {"matches":[...]}
      - nested: {"data":{"rag":{...}}}, {"data":{"result":{...}}}, {"result":{...}}, {"tool_result":{...}}
      - Chroma raw: {"documents":[[...]], "metadatas":[[...]], "distances":[[...]]}
    """
    if not isinstance(res, dict):
        return None

    log.info("[RAG_EXTRACT] Processing response with keys: %s", list(res.keys()))

    # 0) context_snippets 바로 처리
    if isinstance(res.get("context_snippets"), list):
        cs = res["context_snippets"]
        matches = []
        for x in cs:
            if isinstance(x, str):
                matches.append({"text": x, "meta": {}, "score": None})
            elif isinstance(x, dict) and ("text" in x or "chunk" in x):
                txt = x.get("text") or x.get("chunk") or ""
                meta = x.get("meta") or {}
                score = x.get("score")
                matches.append({"text": txt, "meta": meta, "score": score})
        if matches:
            log.info("[RAG_EXTRACT] Found %d matches in context_snippets", len(matches))
            return {"matches": matches}

    # 1) 경로 탐색
    cand_paths: List[List[str]] = [
        ["rag"],
        ["data", "rag"],
        ["data", "result"],
        ["result"],
        ["tool_result", "rag"],
        ["tool_result"],
        ["data", "tool_result"],
    ]

    def dig(d: dict, path: List[str]):
        cur = d
        for key in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        return cur

    for p in cand_paths:
        blob = dig(res, p)
        log.info("[RAG_EXTRACT] Checking path %s: %s", p, type(blob).__name__ if blob else "None")
        
        if isinstance(blob, dict):
            if isinstance(blob.get("matches"), list):
                matches = blob["matches"]
                # 빈 matches도 유효한 결과로 처리 (검색했지만 결과가 없음)
                log.info("[RAG_EXTRACT] Found %d matches in path %s", len(matches), p)
                return {"matches": matches}
            
            # 툴별 결과 처리
            for tool_key, tool_res in blob.items():
                if isinstance(tool_res, dict):
                    if isinstance(tool_res.get("rag"), dict) and isinstance(tool_res["rag"].get("matches"), list):
                        matches = tool_res["rag"]["matches"]
                        log.info("[RAG_EXTRACT] Found %d matches in tool %s", len(matches), tool_key)
                        return {"matches": matches}
            
            docs = blob.get("documents")
            metas = blob.get("metadatas")
            dists = blob.get("distances")
            if isinstance(docs, list) and isinstance(metas, list):
                docs0 = docs[0] if docs and isinstance(docs[0], list) else docs
                metas0 = metas[0] if metas and isinstance(metas[0], list) else metas
                dists0 = dists[0] if dists and isinstance(dists[0], list) else dists
                matches = []
                for i, d in enumerate(docs0):
                    m = metas0[i] if i < len(metas0) else {}
                    s = float(dists0[i]) if dists0 and i < len(dists0) else None
                    matches.append({"text": d, "meta": m, "score": s})
                if matches:
                    log.info("[RAG_EXTRACT] Found %d matches from Chroma format", len(matches))
                    return {"matches": matches}
                    
        if isinstance(blob, list) and blob and isinstance(blob[0], dict) and "text" in blob[0]:
            log.info("[RAG_EXTRACT] Found %d matches in list format", len(blob))
            return {"matches": blob}

    # 2) 최후 수단
    if isinstance(res.get("matches"), list):
        log.info("[RAG_EXTRACT] Found %d matches in top-level matches", len(res["matches"]))
        return {"matches": res["matches"]}

    log.warning("[RAG_EXTRACT] No RAG matches found in response")
    return None


def _extract_final_data(res: dict) -> Optional[dict]:
    """에이전트 응답에서 final_data 추출"""
    if not isinstance(res, dict):
        return None
    
    # 직접 final_data가 있는 경우
    if isinstance(res.get("final_data"), dict):
        return res["final_data"]
    
    # data 하위에 있는 경우
    if isinstance(res.get("data"), dict) and isinstance(res["data"].get("final_data"), dict):
        return res["data"]["final_data"]
    
    # Oracle 결과: data.result 또는 result
    result_data = res.get("result") or (res.get("data", {}) if isinstance(res.get("data"), dict) else {}).get("result")
    if isinstance(result_data, dict):
        # Oracle 결과 구조: {university, year, metric_label, value, ...}
        if "university" in result_data and "value" in result_data:
            return result_data
    
    return None


def _extract_text_response(res: dict) -> Optional[str]:
    """에이전트 응답에서 직접 텍스트 응답 추출"""
    if not isinstance(res, dict):
        return None
    
    # 표준 텍스트 응답 키들
    text_keys = ["final_text", "answer", "text", "message"]
    
    # 최상위 레벨 체크
    for k in text_keys:
        if isinstance(res.get(k), str) and res[k].strip():
            return res[k].strip()
    
    # data 하위 체크
    if isinstance(res.get("data"), dict):
        for k in text_keys:
            v = res["data"].get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    
    return None


# =========================
# 그래프 경로 사용 판단
# =========================
_USERLOCAL_FIELD_TOKENS = [
    "소속대학", "소속 대학",
    "자료구입비", "자료 구입비",
    "예측점수", "점수",
    "학년", "4학년", "3학년", "2학년", "1학년"
]
_PAGE_TOKENS = [
    "학습환경 분석", "발전도 분석", "마이페이지", "내정보", "내 정보", "설정", "대시보드", "메뉴", "페이지"
]
_AND_TOKENS = [" 과 ", " 와 ", " 및 ", " 그리고 ", " 하고 ", " 랑 ", " 이랑 ", ", "]


# 그래프 경로 사용 판단 개선
def _should_use_graph(query: str) -> bool:
    """
    그래프 경로로 보낼지 판단 (강화된 로직):
    - 명시적 연결사 + 복수 요소
    - 비교/계산 키워드
    - 복수 대학/지표 조합
    - 문장부호 기준 2문장 이상
    """
    q = (query or "").strip()
    if not q:
        return False

    # 1) 문장부호 기준 2문장 이상
    sent_splits = [p for p in re.split(r'(?<=[\?\.\!])\s+', q) if p.strip()]
    if len(sent_splits) >= 2:
        return True

    # 2) 명시적 연결사 존재
    conjunctions = [" 과 ", " 와 ", " 및 ", " 그리고 ", " 하고 ", " 랑 ", " 이랑 ", ","]
    has_conjunction = any(conj in q for conj in conjunctions)
    
    # 3) 복수 요소 카운트
    # 학년 수 카운트
    grade_count = len(re.findall(r'([1-4])\s*학년', q))
    
    # 대학 수 카운트
    univ_pattern = re.compile(r'([가-힣A-Za-z]+대학교)')
    univs = [m.group(1) for m in univ_pattern.finditer(q)]
    univ_count = len([u for u in univs if u not in ["어느대학교", "무슨대학교"]])
    
    # 지표 수 카운트
    metrics = ["점수", "예측점수", "자료구입비", "구입비", "대출", "방문"]
    metric_count = sum(1 for metric in metrics if metric in q)
    
    # 4) 비교/계산 키워드
    comparison_keywords = ["비교", "차이", "동일연도", "같은 해", "vs", "대비", "더", "적게", "많이"]
    has_comparison = any(kw in q for kw in comparison_keywords)
    
    # 5) 복합 구조 판단
    total_elements = grade_count + univ_count + metric_count
    
    # 그래프 경로 조건들
    conditions = [
        has_conjunction and total_elements >= 2,    # 연결사 + 복수 요소
        has_comparison and total_elements >= 1,     # 비교 키워드 + 요소
        univ_count >= 2,                            # 복수 대학
        grade_count >= 2,                           # 복수 학년
        metric_count >= 2,                          # 복수 지표
        total_elements >= 3,                        # 전체 요소 3개 이상
        len(q) >= 60 and q.count(",") >= 2,        # 긴 문장 + 쉼표
        # "내 것과 XX대학교" 패턴
        (any(self_word in q for self_word in ["내", "나의"]) and univ_count >= 1)
    ]
    
    return any(conditions)


def _scale_max_tokens(base_max_new: int, num_units: int, is_agent: bool = False) -> int:
    """
    복합 요청(유닛/태스크 수)에 비례하여 max_new_tokens를 확대.
    - 기본 확대: +60 * (units-1)
    - 에이전트 경로면 최소 320 보장
    - 상한선은 800 (과도한 생성 방지)
    """
    units = max(1, int(num_units))
    scaled = base_max_new + 60 * (units - 1)
    if is_agent:
        scaled = max(320, scaled)
    return min(800, max(120, int(scaled)))


# =========================
# 진입점
# =========================
def handle(router, cfg: dict, repo, inp: OrchestratorInput) -> OrchestratorOutput:
    """
    LangGraph 기반 멀티-질문 분해/실행 → 조립을 우선 시도하고,
    실패하거나 단문이면 기존 단일 분기 로직으로 폴백
    """
    # 1) 1차 의도 분류
    intent = intent_classifier.classify(inp.query, inp.usr_id)
    ilog.info(
        "[INTENT] usr_id=%r conv_id=%r kind=%s reason=%s slots=%d calc=%s external=%s",
        inp.usr_id, inp.conv_id,
        intent.kind, intent.reason,
        len(intent.user_slots or []),
        intent.wants_calculation,
        intent.external_entities,
    )

    # 1-1) 🔸 오버라이드 로직 수정: 복합 질문은 제외
    if inp.usr_id:
        try:
            # 지연 임포트: 의존 최소화
            from .intent_classifier import extract_slots_light
            _slots = extract_slots_light(inp.query) or {}
        except Exception:
            _slots = {}
        
        # 🔥 복합 질문 체크: 외부 대학이나 복잡한 구조가 있으면 오버라이드 하지 않음
        has_external_entity = bool(intent.external_entities)
        has_comparison = any(kw in inp.query for kw in ["비교", "차이", "동일연도", "같은 해", "와", "과", "그리고"])
        is_complex_query = intent.wants_calculation or has_external_entity or has_comparison
        
        # 단순한 개인 데이터 질의만 오버라이드
        if (not is_complex_query and 
            _slots.get("owner") == "self" and 
            _slots.get("metric") in {"cps", "lps", "vps", "score", "budget", "자료구입비"}):
            
            log.info("[PATH] override → user_local (owner=self, metric=%s)", _slots.get("metric"))
            body, prof = local_exec.run_user_local(router, cfg, repo, inp.usr_id, inp.query, inp.overrides)
            return OrchestratorOutput(
                answer=body,
                route="local_user",
                meta={"intent": intent.dict(), "profile": prof, "override": "self_metric"}
            )
        elif is_complex_query:
            log.info("[PATH] complex query detected, skipping override (external=%s, calc=%s, comparison=%s)", 
                     has_external_entity, intent.wants_calculation, has_comparison)

    # 2) 그래프 경로 우선 (태스크 수 기반 토큰 스케일링 적용)
    try:
        if AGENT_ENABLED and _should_use_graph(inp.query):
            log.info("[PATH] attempting graph route")
            # 태스크 수 미리 추정하여 토큰 스케일링
            from .graph import plan_tasks, run_orchestrator_graph  # 지연 임포트
            tasks_preview = plan_tasks(inp.query, inp.usr_id)
            base_max_new = int((inp.overrides or {}).get("max_new_tokens", cfg.get("generation", {}).get("max_new_tokens", 180)))
            scaled_tokens = _scale_max_tokens(base_max_new, len(tasks_preview), is_agent=False)
            ov_for_graph = dict(inp.overrides or {})
            ov_for_graph["max_new_tokens"] = scaled_tokens

            # 스케일된 overrides로 새 입력 구성
            inp_for_graph = OrchestratorInput(
                query=inp.query,
                usr_id=inp.usr_id,
                conv_id=inp.conv_id,
                first_turn=inp.first_turn,
                overrides=ov_for_graph,
                headers=inp.headers,
                meta=inp.meta
            )

            body, tasks, results = run_orchestrator_graph(router, cfg, repo, inp_for_graph)
            meta = {
                "intent": intent.dict(),
                "graph": {
                    "task_count": len(tasks),
                    "executors": [t.get("executor") for t in tasks],
                }
            }
            log.info("[PATH] route=graph tasks=%d executors=%s",
                     len(tasks), ",".join(meta["graph"]["executors"]))
            return OrchestratorOutput(answer=body, route="graph", meta=meta)
        else:
            log.info("[PATH] graph route not eligible (agent_enabled=%s, should_use_graph=%s)", 
                     AGENT_ENABLED, _should_use_graph(inp.query))
    except Exception as e:
        log.warning("[GRAPH] orchestration failed → fallback. reason=%s", e)

    # 3) 단일 경로 폴백
    if intent.kind == "guest_base_chat":
        log.info("[PATH] route=guest_base_chat")
        body = local_exec.run_guest_base_chat(router, cfg, inp.query, inp.overrides)
        return OrchestratorOutput(answer=body, route="guest_base_chat", meta={"intent": intent.dict()})

    if intent.kind == "user_local":
        log.info("[PATH] route=local_user (user_data_chain)")
        body, prof = local_exec.run_user_local(router, cfg, repo, inp.usr_id, inp.query, inp.overrides)
        return OrchestratorOutput(answer=body, route="local_user", meta={"intent": intent.dict(), "profile": prof})

    if intent.kind == "base_chat":
        log.info("[PATH] route=base_chat")
        body, prof = local_exec.run_user_base_chat(router, cfg, repo, inp.usr_id, inp.conv_id or 0, inp.query, inp.overrides)
        return OrchestratorOutput(answer=body, route="base_chat", meta={"intent": intent.dict(), "profile": prof})

    # === agent_needed ===
    if not AGENT_ENABLED:
        log.info("[PATH] route=agent_needed_disabled (agent off)")
        return OrchestratorOutput(
            answer="기능에 문제가 있습니다. 잠시 후 다시 시도해주세요!",
            route="agent_needed_disabled",
            meta={"intent": intent.dict()}
        )

    log.info("[PATH] route=agent_needed")
    try:
        payload = planner.make_agent_payload(intent, inp.query, inp.usr_id, inp.conv_id, inp.meta.get("session", {}))
        log.info("[AGENT_CALL] payload keys: %s", list(payload.keys()))
        res = agent_client.plan_and_run(payload)

        log.info("[AGENT_RES] response keys: %s", list(res.keys()) if isinstance(res, dict) else type(res).__name__)
        
        # 에이전트 응답 디버깅
        if isinstance(res, dict):
            if "data" in res:
                log.info("[AGENT_RES] data keys: %s", list(res["data"].keys()) if isinstance(res["data"], dict) else type(res["data"]).__name__)
            if "tool_result" in res:
                log.info("[AGENT_RES] tool_result keys: %s", list(res["tool_result"].keys()) if isinstance(res["tool_result"], dict) else type(res["tool_result"]).__name__)

        # 1) RAG 우선 - 빈 결과도 처리
        rag = _extract_rag_blob(res)
        if rag is not None:  # matches가 빈 리스트라도 처리
            matches = rag.get("matches", [])
            if matches:
                # 매치가 있는 경우: 정상 합성
                usr_name, usr_snm = ("게스트", "")
                if inp.usr_id:
                    try:
                        prof = repo.get_user_profile(inp.usr_id)
                        usr_name, usr_snm = prof if prof else ("사용자", "")
                    except Exception:
                        pass
                # 에이전트 경로: 토큰 여유를 더 준다(최소 320, 복합 요청이면 비례 증가)
                base_max_new = int((inp.overrides or {}).get("max_new_tokens", cfg.get("generation", {}).get("max_new_tokens", 180)))
                # RAG에선 태스크 수 알기 어렵지만 긴 답변 대비 +2 유닛 가정
                scaled_tokens = _scale_max_tokens(base_max_new, num_units=3, is_agent=True)
                ov2 = dict(inp.overrides or {})
                ov2["max_new_tokens"] = scaled_tokens
                answer = _synthesize_from_rag(router, cfg, inp.query, rag, ov2, usr_name=usr_name, usr_snm=usr_snm)
                log.info("[AGENT_SUCCESS] RAG synthesis completed, answer length: %d", len(answer))
                return OrchestratorOutput(answer=answer, route="agent_rag", meta={"intent": intent.dict(), "agent_raw": res})
            else:
                # 검색했지만 결과가 없는 경우
                log.info("[AGENT_RAG] No matches found in RAG result")
                answer = "죄송합니다. 관련 정보를 찾지 못했습니다."
                return OrchestratorOutput(answer=answer, route="agent_rag_empty", meta={"intent": intent.dict(), "agent_raw": res})

        # 2) final_data (Oracle 결과 등)
        final_data = _extract_final_data(res)
        if final_data:
            log.info("[AGENT_SUCCESS] Found final_data: %s", list(final_data.keys()))
            
            # Oracle 대학 데이터 결과 포맷팅
            if "university" in final_data and "value" in final_data:
                univ = final_data.get("university", "")
                year = final_data.get("year", "")
                metric = final_data.get("metric_label", "지표")
                value = final_data.get("value")
                
                if value is not None:
                    answer = f"{year}년도 {univ}의 {metric}는 {value}입니다."
                else:
                    answer = f"{year}년도 {univ}의 {metric} 데이터를 찾을 수 없습니다."
                
                return OrchestratorOutput(answer=answer, route="agent_oracle", meta={"intent": intent.dict(), "agent_raw": res})
            
            # 기타 계산형 결과
            numeric_keys = any(k in final_data for k in ("user_value", "benchmark", "diff", "ratio"))
            if numeric_keys:
                unit = final_data.get("unit", "")
                txt = []
                if "user_value" in final_data: txt.append(f"사용자 값: {final_data['user_value']}{unit}")
                if "benchmark" in final_data:  txt.append(f"비교 기준: {final_data['benchmark']}{unit}")
                if "diff" in final_data:       txt.append(f"차이: {final_data['diff']}{unit}")
                if "ratio" in final_data:      txt.append(f"비율: {final_data['ratio']:.4f}")
                answer = "\n".join(txt) if txt else "계산 결과를 가져왔습니다."
                return OrchestratorOutput(answer=answer, route="agent_calc", meta={"intent": intent.dict(), "agent_raw": res})

        # 3) 에이전트가 직접 텍스트 응답을 준 경우
        text_response = _extract_text_response(res)
        if text_response:
            log.info("[AGENT_SUCCESS] Found text response, length: %d", len(text_response))
            return OrchestratorOutput(answer=text_response, route="agent_text", meta={"intent": intent.dict(), "agent_raw": res})

        # 4) 에러 응답 처리
        if isinstance(res, dict) and not res.get("ok", True):
            error_msg = res.get("error", "알 수 없는 오류가 발생했습니다.")
            log.warning("[AGENT_ERROR] Agent returned error: %s", error_msg)
            return OrchestratorOutput(answer=f"죄송합니다. {error_msg}", route="agent_error", meta={"intent": intent.dict(), "agent_raw": res})

        # 5) 기타 폴백
        log.warning("[AGENT_FALLBACK] No usable response found in agent result")
        log.debug("[AGENT_FALLBACK] Full response: %s", res)
        return OrchestratorOutput(answer="죄송합니다. 요청을 처리하는 데 문제가 발생했습니다.", route="agent", meta={"intent": intent.dict(), "agent_raw": res})

    except Exception as e:
        log.exception("[AGENT_ERROR] Agent call failed: %s", e)
        return OrchestratorOutput(
            answer="기능에 문제가 있습니다. 잠시 후 다시 시도해주세요!",
            route="agent_call_failed",
            meta={"intent": intent.dict(), "error": str(e)}
        )