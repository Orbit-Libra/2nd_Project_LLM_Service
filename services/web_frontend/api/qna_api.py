# services/web_frontend/api/qna_api.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime, timedelta
import random, re

qna_bp = Blueprint(
    "qna",
    __name__,
    url_prefix="/qna",
    template_folder="../templates",
    static_folder="../static"
)

# ─────────────────────────────────────────────────────
# 메모리 저장소(배포 전 임시) + 더미 데이터 100개 자동 시딩
# ─────────────────────────────────────────────────────
_QNA_MEMORY = []  # [{id, kind, is_public, title, has_file, author, created_at, status, email, content}, ...]

def _is_valid_email(v: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v or ""))

def _mask_name(name: str) -> str:
    # 김철수 -> 김**, 이가빈 -> 이**
    return (name[:1] + "**") if name else "**"

def _seed_if_empty():
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
            "author": _mask_name(random.choice(["김영호","박민정","이수진","문지호","강민수","윤해솔","오지훈"])),
            "created_at": dt,
            "status": random.choice(statuses),
            "email": "user{}@example.com".format(i),
            "content": "샘플 문의 내용입니다. {}".format(i)
        })
    # 최신이 뒤에 있어도 역순 정렬은 라우트에서 처리
_seed_if_empty()

# ─────────────────────────────────────────────────────
# 목록 + 페이지네이션
# ─────────────────────────────────────────────────────
@qna_bp.get("/")
def qna_list():
    # 정렬: 최신순(날짜 내림차순)
    data = sorted(_QNA_MEMORY, key=lambda x: (x["created_at"], x["id"]), reverse=True)

    # 페이지네이션
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    per_page = 10
    total = len(data)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    end = start + per_page
    rows = data[start:end]

    # 화면용 번호(역순): total, page, per_page 기준으로 계산
    # 첫 행 번호 = total - start
    start_no = total - start

    return render_template("qna/list.html",
                           items=rows,
                           page=page, pages=pages, per_page=per_page, total=total, start_no=start_no)

# ─────────────────────────────────────────────────────
# 작성 폼
# ─────────────────────────────────────────────────────
@qna_bp.get("/new")
def qna_new():
    return render_template("qna/question.html")

# ─────────────────────────────────────────────────────
# 작성 처리(서버 검증)
# ─────────────────────────────────────────────────────
@qna_bp.post("/new")
def qna_create():
    title   = (request.form.get("title") or "").strip()
    email   = (request.form.get("email") or "").strip()
    content = (request.form.get("content") or "").strip()
    agree   = request.form.get("agree") == "on"

    errors = {}
    if not title: errors["title"] = "제목은 필수입니다."
    if not email or not _is_valid_email(email): errors["email"] = "유효한 이메일을 입력하세요."
    if not content or len(content) < 10: errors["content"] = "문의 내용은 10자 이상 입력하세요."
    if not agree: errors["agree"] = "개인정보 수집 및 이용에 동의해주세요."

    if errors:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "errors": errors}), 400
        flash("입력값을 확인해주세요.", "error")
        return render_template("qna/question.html",
                               form={"title": title, "email": email, "content": content},
                               errors=errors)

    new_id = (max([r["id"] for r in _QNA_MEMORY]) + 1) if _QNA_MEMORY else 1
    _QNA_MEMORY.append({
        "id": new_id,
        "kind": "일반",
        "is_public": True,
        "title": title,
        "has_file": False,
        "author": _mask_name(email.split("@")[0]),
        "created_at": datetime.now(),
        "status": "처리중",
        "email": email,
        "content": content
    })

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "redirect": url_for("qna.qna_list")})

    return redirect(url_for("qna.qna_list"))
