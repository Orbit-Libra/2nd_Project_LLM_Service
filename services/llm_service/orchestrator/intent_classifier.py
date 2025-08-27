import re
from typing import List
from .schemas import Intent, UserDataSlot
from . import tool_hints

# 지표 시소너리(동의어 → 정규화)
METRIC_ALIASES = {
    "purchase_cost": ["자료구입비", "구입비", "구입 비용", "cps", "CPS"],
    "loans":        ["대출", "대출건수", "대출 건수", "LPS", "lps"],
    "visits":       ["방문수", "방문 수", "방문횟수", "방문 횟수", "출입", "출입 수", "VPS", "vps", "도서관 방문", "도서관 방문수"],
    "score":        ["점수", "예측점수", "예측 점수", "스코어", "score", "SCR_EST", "scr_est"],
}

# 산술/복수 요청 트리거(한국어 보강)
CALC_TRIGGERS = [
    "차이", "증감", "증감률", "증가율", "퍼센트", "%", "비율", "비교",
    "+", "-", "*", "/", "합", "합계", "합하면", "합치면", "더하면", "더해", "더해줘", "더하기",
    "각각", "둘다", "둘 다"
]

# 연결사(복수 슬롯 힌트)
CONJ_TOKENS = ["와", "과", "하고", "및", "랑", "그리고"]

SELF_TOKENS = ["내", "나의", "제가", "내가"]

GRADE_RE = re.compile(r'([1-4])\s*학년')
UNIV_RE  = re.compile(r'([가-힣A-Za-z]+대학교)')

def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(k in text for k in keywords)

def _normalize_metrics(text: str) -> List[str]:
    hits = []
    for canon, aliases in METRIC_ALIASES.items():
        if _contains_any(text, aliases):
            hits.append(canon)
    return list(dict.fromkeys(hits))  # 중복 제거/순서 유지

def _extract_grades(text: str) -> List[int]:
    return [int(m.group(1)) for m in GRADE_RE.finditer(text)]

def _extract_universities(text: str) -> List[str]:
    return list({m.group(1) for m in UNIV_RE.finditer(text)})

def classify(query: str, usr_id: str | None) -> Intent:
    q = (query or "").strip()

    # ❶ “서비스 이용/네비게이션” 질문 → 항상 RAG 에이전트
    if tool_hints.detect_usage_guide(q):
        return Intent(
            kind="agent_needed",
            reason="usage_guide_rag",
            capabilities_hint=["rag_search"],
            user_slots=[],
            wants_calculation=False,
            external_entities=[],
            rag_group_hint=tool_hints.group_hint_for_usage(q),
        )

    # ❷ 여기서부터 기존 규칙
    metrics = _normalize_metrics(q)
    grades  = _extract_grades(q)
    univs   = _extract_universities(q)

    wants_calc = _contains_any(q, CALC_TRIGGERS)
    has_conj   = _contains_any(q, CONJ_TOKENS)

    # 게스트: (가이드가 아니면) 기본 베이스챗
    if not usr_id:
        return Intent(kind="guest_base_chat", reason="no_user_session")

    # 암묵적 self: 외부 대학명 없고, 지표/학년이 함께 언급되면 '내 데이터'로 추정
    explicit_self = _contains_any(q, SELF_TOKENS)
    implied_self  = (not explicit_self) and (not univs) and (metrics != []) and (grades != [])

    # 슬롯 구성
    slots: List[UserDataSlot] = []
    if metrics:
        if grades:
            for g in grades:
                for m in metrics:
                    slots.append(UserDataSlot(metric=m, grade=g, owner="self" if (explicit_self or implied_self) else "other"))
        else:
            for m in metrics:
                slots.append(UserDataSlot(metric=m, grade=None, owner="self" if (explicit_self or implied_self) else "other"))

    # 분기
    if explicit_self or implied_self:
        if univs:
            return Intent(
                kind="agent_needed",
                reason="self data + external entity",
                capabilities_hint=["oracle_fetch","data_service_fetch","calculator"],
                user_slots=slots, wants_calculation=True, external_entities=univs
            )
        if len(slots) >= 2 or wants_calc or has_conj:
            return Intent(
                kind="agent_needed",
                reason="multi-slot or calculation",
                capabilities_hint=["oracle_fetch","calculator"],
                user_slots=slots, wants_calculation=True, external_entities=[]
            )
        if len(slots) == 1 and not wants_calc:
            return Intent(
                kind="user_local",
                reason="single self metric (no calc/external)",
                user_slots=slots, wants_calculation=False, external_entities=[]
            )

    if univs:
        return Intent(
            kind="agent_needed",
            reason="external entity present",
            capabilities_hint=["data_service_fetch","rag_search","calculator"],
            user_slots=slots, wants_calculation=wants_calc or has_conj, external_entities=univs
        )

    if metrics:
        return Intent(kind="base_chat", reason="metric mentioned but self unclear",
                      user_slots=slots, wants_calculation=wants_calc)

    return Intent(kind="base_chat", reason="general chat")
