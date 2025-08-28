# services/llm_service/orchestrator/intent_classifier.py
import re
from typing import List
from .schemas import Intent, UserDataSlot
from . import tool_hints

UNIV_NAME_RE = re.compile(r'([가-힣A-Za-z]+대학교)')

def _extract_entity(text: str) -> str | None:
    # "서울대학교의" 같은 소유격/조사 제거
    m = UNIV_NAME_RE.search(text or "")
    if not m:
        return None
    ent = m.group(1)
    # "어느대학교/무슨대학교" 제거
    if any(x in ent for x in ["어느대학교","무슨대학교"]):
        return None
    return ent

def extract_slots_light(query: str) -> dict:
    """
    절 단위 슬롯(라이트 버전):
    - metric: cps|lps|vps|score|affiliation|guide|budget 등
    - owner: self|other|none
    - entity: 대학명
    - year: 20xx (선택)
    - grade: 1~4 (선택)
    - mode: guide|data
    - ref: same_year|previous_task|none
    """
    q = (query or "").strip()
    year = None
    m_y = re.search(r'(\d{4})\s*년', q)
    if m_y:
        year = int(m_y.group(1))

    grade = None
    m_g = re.search(r'([1-4])\s*학년', q)
    if m_g:
        grade = int(m_g.group(1))

    # owner/entity
    explicit_self = any(tok in q for tok in ["내 ", "나의 ", "내의 ", "우리 "])
    entity = _extract_entity(q)
    owner = "self" if explicit_self else ("other" if entity else "none")

    # mode
    is_guide = any(k in q for k in ["수정", "변경", "방법", "하는 법", "어디서", "페이지", "경로", "버튼", "탭"])
    mode = "guide" if is_guide else "data"

    # metric (얕은 규칙)
    metric = None
    if any(k in q for k in ["소속대학","소속 대학","내 대학","내 대학교"]):
        metric = "affiliation"
    elif any(k in q for k in ["CPS","자료구입비","자료 구입비","구입비"]):
        metric = "cps"
    elif any(k in q for k in ["LPS","대출","대출건수","대출 건수"]):
        metric = "lps"
    elif any(k in q for k in ["VPS","방문","방문자","방문 수","방문수"]):
        metric = "vps"
    elif any(k in q for k in ["점수","예측점수","score","SCR"]):
        metric = "score"
    elif any(k in q for k in ["예산","budget","BGT"]):
        metric = "budget"

    # ref (동일연도/앞의)
    ref = "none"
    if any(k in q for k in ["동일연도", "같은 해", "그 해", "동일 년도"]):
        ref = "same_year"
    elif any(k in q for k in ["앞의", "이전", "첫번째", "첫 번째"]):
        ref = "previous_task"

    return {
        "metric": metric,
        "owner": owner,
        "entity": entity,
        "year": year,
        "grade": grade,
        "mode": mode,
        "ref": ref
    }

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
UNIV_RE  = re.compile(r'([가-힣A-Za-z]{2,}대학교)')  # 최소 2글자 + "대학교" (어느/무슨 등 제외 목적)
GENERIC_UNIV_TOKENS = {"어느대학교", "무슨대학교", "어느 대학교", "무슨 대학교", "내 대학교", "내 대학"}

PROFILE_KEYWORDS = [
    "소속대학", "소속 대학", "소속학교", "소속 학교",
    "내 소속", "나의 소속", "내 대학", "내 대학교",
    "소속이 어디", "소속이 어딘지", "소속대학이 어디", "소속대학이 어느"
]

AFFILIATION_TOKENS = ["소속대학", "소속 대학", "내 대학", "내 대학교", "나의 대학", "나의 대학교"]

def _is_affiliation_query(q: str) -> bool:
    qn = (q or "").strip()
    if not qn:
        return False
    if any(tok in qn for tok in AFFILIATION_TOKENS):
        return True
    # “내 + (대학|대학교)?” 패턴도 허용
    import re
    return bool(re.search(r"(내|나의).*(대학|대학교)", qn))

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
    # 원래 함수 교체
    raw = [m.group(1) for m in UNIV_RE.finditer(text or "")]
    # 포괄/지시 표현 제거
    cleaned = []
    for t in raw:
        if t in GENERIC_UNIV_TOKENS:  # "어느대학교" 등
            continue
        # "내/우리/무슨/어느"가 바로 앞에 오는 패턴 방지
        if re.search(r'(내|우리|무슨|어느)\s*' + re.escape(t), text):
            continue
        cleaned.append(t)
    return list(dict.fromkeys(cleaned))

def classify(query: str, usr_id: str | None) -> Intent:
    q = (query or "").strip()

    # ❶ 서비스 이용/네비 → RAG
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

    # 🔸 신규: 소속대학 질의는 프로필 조회이므로 user_local 고정
    if usr_id and _is_affiliation_query(q):
        return Intent(
            kind="user_local",
            reason="self affiliation",
            capabilities_hint=[],
            user_slots=[UserDataSlot(metric="affiliation", grade=None, owner="self")],
            wants_calculation=False,
            external_entities=[]
        )
        
    # ❸ 기존 규칙
    metrics = _normalize_metrics(q)
    grades  = _extract_grades(q)
    univs   = _extract_universities(q)

    wants_calc = _contains_any(q, CALC_TRIGGERS)
    has_conj   = _contains_any(q, CONJ_TOKENS)

    if not usr_id:
        return Intent(kind="guest_base_chat", reason="no_user_session")

    explicit_self = _contains_any(q, SELF_TOKENS)
    implied_self  = (not explicit_self) and (not univs) and (metrics != []) and (grades != [])

    slots: List[UserDataSlot] = []
    if metrics:
        if grades:
            for g in grades:
                for m in metrics:
                    slots.append(UserDataSlot(metric=m, grade=g, owner="self" if (explicit_self or implied_self) else "other"))
        else:
            for m in metrics:
                slots.append(UserDataSlot(metric=m, grade=None, owner="self" if (explicit_self or implied_self) else "other"))

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
