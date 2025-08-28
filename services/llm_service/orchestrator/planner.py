# services/llm_service/orchestrator/planner.py
from typing import Dict, Any
from .schemas import Intent

def make_agent_payload(intent: Intent, query: str, usr_id: str, conv_id: int | None, session_meta: dict) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "query": query,
        "user_context": {
            "user_id": usr_id,
            "session": session_meta or {},
            "permissions": ["read:own_data", "read:public_stats"],
        },
        "hints": intent.capabilities_hint or [],
        "locale": "ko-KR",
        "conv_id": conv_id,
        "slots": [s.dict() for s in intent.user_slots],
        "wants_calculation": intent.wants_calculation,
        "external_entities": intent.external_entities,
    }

    if intent.rag_group_hint:
        payload["rag"] = {"group_hint": intent.rag_group_hint, "top_k": 5}

    # 🔸 NEW: 외부 대학 데이터 → ORACLE 우선 (로그인 사용자만)
    if usr_id and intent.external_entities:
        # 1) RAG 힌트 제거(중복/충돌 방지)
        payload["hints"] = [h for h in (payload.get("hints") or []) if not str(h).startswith("rag_")]

        # 2) ORACLE 힌트 주입
        hints = set(payload.get("hints") or [])
        hints.add("oracle_univ_data")
        payload["hints"] = list(hints)

        # 3) (선택) 툴 제안 – agent_service가 'tool_suggestions'를 존중하도록
        payload["tool_suggestions"] = [{
            "tool": "oracle.query_university_metric",
            "args": {
                "university": intent.external_entities[0],
                # metric/year는 agent가 추가 파싱/보강 (혹은 그래프에서 넘김)
            }
        }]

    return payload
