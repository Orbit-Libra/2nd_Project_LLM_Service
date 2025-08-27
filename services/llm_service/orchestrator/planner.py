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
    # RAG 힌트(컬렉션 그룹)
    if intent.rag_group_hint:
        payload["rag"] = {
            "group_hint": intent.rag_group_hint,
            "top_k": 5
        }
    return payload
