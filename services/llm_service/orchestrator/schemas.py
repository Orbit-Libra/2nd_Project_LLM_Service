# services/llm_service/orchestrator/schema.py
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Literal

IntentKind = Literal["guest_base_chat", "user_local", "base_chat", "agent_needed"]

class UserDataSlot(BaseModel):
    metric: str            # "purchase_cost" | "visits" | "loans" | "score" 등
    grade: Optional[int]   # 1~4
    owner: Literal["self","other"] = "self"  # 기본 self

class Intent(BaseModel):
    kind: IntentKind
    reason: str = ""
    capabilities_hint: List[str] = []
    user_slots: List[UserDataSlot] = []    # 추출된 유저데이터 슬롯들
    wants_calculation: bool = False        # 산술/비교 여부
    external_entities: List[str] = []      # "서울대학교" 등 외부 타겟
    # RAG 전용 힌트(예: 컬렉션 그룹명)
    rag_group_hint: Optional[str] = None

class OrchestratorInput(BaseModel):
    query: str
    usr_id: Optional[str] = None
    conv_id: Optional[int] = None
    first_turn: bool = False
    overrides: Dict[str, Any] = {}
    headers: Dict[str, str] = {}
    meta: Dict[str, Any] = {}         # e.g., {"client":"web","locale":"ko-KR"}

class OrchestratorOutput(BaseModel):
    answer: str
    route: str
    meta: Dict[str, Any] = {}
