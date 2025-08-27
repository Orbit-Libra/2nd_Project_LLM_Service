# services/llm_service/orchestrator/tool_hints.py
import re

# “서비스 이용법/네비게이션/페이지 이동” 류 키워드
GUIDE_KEYWORDS = [
    "이용법", "사용법", "사용 방법", "이용 방법", "어떻게 써", "어떻게 사용",
    "어디서", "어디에서", "어디로 이동", "어디로 가", "어디로 들어가", "어디로 가면",
    "페이지", "화면", "메뉴", "탭", "버튼", "경로",
    "개인정보", "개인 정보", "회원정보", "회원 정보", "프로필", "비밀번호",
    "회원가입", "가입", "로그인", "로그 아웃", "마이페이지", "마이 페이지",
    "예측점수", "예측 점수", "대출", "방문수", "자료구입비"
]

# 특정 가이드 문서 그룹 힌트(파일명/컬렉션명 기준)
DEFAULT_GUIDE_GROUP = "서비스이용가이드"

def detect_usage_guide(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    # 간단: 위 키워드가 하나라도 포함되면 가이드성으로 간주
    return any(k in q for k in GUIDE_KEYWORDS)

def group_hint_for_usage(query: str) -> str:
    # 필요 시 질문에서 더 구체화 가능. 지금은 단일 컬렉션으로 고정.
    return DEFAULT_GUIDE_GROUP
