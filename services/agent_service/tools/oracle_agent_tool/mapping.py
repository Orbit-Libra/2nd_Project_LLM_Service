# services/agent_service/tools/oracle_agent_tool/mapping.py
# -*- coding: utf-8 -*-
"""
사람이 묻는 용어 → 코드 스니펫 매핑.
예: "자료구입비" -> "MC", "재학생 1인당 자료구입비" -> "CPS"
"""
LABEL_TO_CODE = {
    "자료구입비": "MC",
    "자료구입비(결산)": "MCS",
    "자료구입비계": "MCT",
    "재학생 1인당 자료구입비": "CPS",
    "재학생 1인당 자료구입비(결산)": "CPSS",
    "재학생 1인당 도서관방문자수": "VPS",
    "재학생 1인당 대출책수": "LPS",
    "예산": "BGT",
    "대학총예산": "UBGT",
    "대학총결산": "USTL",
    "대학총결산 대비 자료구입비 비율": "BRT",
    "학교명": "SNM",
    "연도": "YR",
    # 필요시 계속 확장
}

# 사람이 말하는 동의어/키워드 → 표준 라벨
ALIASES = {
    # 자료구입비 군
    "자료 구입비": "자료구입비",
    "구입비": "자료구입비",
    "도서자료 구입비": "자료구입비",
    "전자자료 구입비": "전자자료 구입비",  # (별도 컬럼 필요 시 확장)
    "예산": "예산",
    "budget": "예산",

    # 1인당 지표
    "CPS": "재학생 1인당 자료구입비",
    "LPS": "재학생 1인당 대출책수",
    "VPS": "재학생 1인당 도서관방문자수",
}

def normalize_metric_label(human_text: str) -> str | None:
    """
    자연어 질의에서 메트릭 라벨을 표준 라벨로 치환.
    """
    t = (human_text or "").strip()
    if not t:
        return None
    # 우선 완전 일치
    if t in LABEL_TO_CODE:
        return t
    # 별칭 매핑
    if t in ALIASES:
        return ALIASES[t]
    # 부분 문자열 휴리스틱
    if "CPS" in t.upper():
        return "재학생 1인당 자료구입비"
    if "LPS" in t.upper():
        return "재학생 1인당 대출책수"
    if "VPS" in t.upper():
        return "재학생 1인당 도서관방문자수"
    if "구입비" in t or "자료 구입" in t:
        return "자료구입비"
    if "예산" in t:
        return "예산"
    return None

def code_for_label(label: str) -> str | None:
    return LABEL_TO_CODE.get(label)
