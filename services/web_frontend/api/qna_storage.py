#services/web_frontend/api/qna_storage.py
#메모리 저장/시드/도우미/댓글

from datetime import datetime, timedelta
import random, re

# 메모리 저장(임시)
_QNA_MEMORY = []     # [{id, kind, is_public, title, has_file, author, created_at, status, email, content}]
_QNA_COMMENTS = {}   # { qid: [ {id, parent_id, author, content, created_at, is_admin} ] }

def is_valid_email(v: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v or ""))

def mask_name(name: str) -> str:
    return (name[:1] + "**") if name else "**"

def seed_if_empty():
    if _QNA_MEMORY:
        return
    titles = [
        "대출 연장 관련", "회원 탈퇴에 관한건", "(2025)학교정보공개 관련 문의", "답글 확인",
        "로그인관련", "잘안되는데 고장인가요", "로그인 시 회원증 발급 되나여?",
        "7월 10일 문의 건 미처리에 대한 문의"
    ]
    kinds = ["일반", "민원"]
    statuses = ["답변완료", "처리중"]
    today = datetime.now()
    for i in range(1, 101):
        dt = today - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
        _QNA_MEMORY.append({
            "id": i,
            "kind": random.choice(kinds),
            "is_public": random.choice([True, False]),
            "title": random.choice(titles),
            "has_file": random.choice([True, False, False]),
            "author": mask_name(random.choice(["김영호","박민정","이수진","문지호","강민수","윤해솔","오지훈"])),
            "created_at": dt,
            "status": random.choice(statuses),
            "email": f"user{i}@example.com",
            "content": f"샘플 문의 내용입니다. {i}"
        })

def items_sorted():
    return sorted(_QNA_MEMORY, key=lambda x: (x["created_at"], x["id"]), reverse=True)

def next_id():
    return (max([r["id"] for r in _QNA_MEMORY]) + 1) if _QNA_MEMORY else 1

def add_item(item: dict):
    _QNA_MEMORY.append(item)

def get_item(qid: int):
    return next((x for x in _QNA_MEMORY if x["id"] == qid), None)

# 댓글 관련
def comments_of(qid: int):
    return _QNA_COMMENTS.get(qid, [])

def add_comment(qid: int, author: str, content: str, parent_id=None, is_admin=False):
    lst = _QNA_COMMENTS.setdefault(qid, [])
    cid = (max([c["id"] for c in lst]) + 1) if lst else 1
    lst.append({
        "id": cid,
        "parent_id": parent_id,
        "author": author or "익명",
        "content": content,
        "created_at": datetime.now(),
        "is_admin": is_admin
    })
    return cid

def build_tree(comments):
    kids = {}
    for c in comments:
        kids.setdefault(c["parent_id"], []).append(c)
    def walk(pid=None, depth=0):
        arr = []
        for c in kids.get(pid, []):
            c2 = c.copy(); c2["depth"] = depth
            arr.append(c2)
            arr.extend(walk(c["id"], depth+1))
        return arr
    return walk(None, 0)
