#services/web_frontend/api/qna_list.py
#목록/페이지네이션(템플릿 라우트)
from flask import render_template, request
from .qna import qna_bp
from .qna_storage import seed_if_empty, items_sorted
from urllib.parse import urlencode

@qna_bp.get("/")
def qna_list():
    seed_if_empty()
    data = items_sorted()
    # 정렬: 최신순(날짜 내림차순)
    # data = sorted(_QNA_MEMORY, key=lambda x: (x["created_at"], x["id"]), reverse=True)

    # ---- 필터 파라미터 수집 ----
    args   = request.args.to_dict(flat=True)
    kind   = (args.get("kind") or "").strip()       # "일반" / "민원" / ""
    public = (args.get("public") or "").strip()     # "1" / "0" / ""
    status = (args.get("status") or "").strip()     # "답변완료" / "처리중" / ""
    field  = (args.get("field") or "title").strip() # 기본 title
    q      = (args.get("q") or "").strip()

    # ---- 필터 적용 ----
    if kind:
        data = [d for d in data if d["kind"] == kind]
    if public in ("1", "0"):
        want = (public == "1")
        data = [d for d in data if d["is_public"] is want]
    if status:
        data = [d for d in data if d["status"] == status]
    if q:
        if field == "title":
            data = [d for d in data if q in d["title"]]
        elif field == "author":
            data = [d for d in data if q in d["author"]]    
            
    # 페이지네이션(10개 윈도우) 
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    per_page = 10
    total = len(data)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    rows = data[start:start+per_page]
    start_no = total - start  # 역순 번호
    
    # 숫자 윈도우: 항상 10칸(1~10, 11~20…)
    window = 10
    start_page = ((page - 1) // window) * window + 1
    end_page   = min(start_page + window - 1, pages)

    # 페이징/링크에 기존 필터 유지용 쿼리스트링
    base_args = {k: v for k, v in args.items() if k != "page" and v not in (None, "",)}
    query_base = urlencode(base_args)

    sel = {"kind": kind, "public": public, "status": status, "field": field, "q": q}
    
    return render_template("qna/list.html",
                           items=rows, page=page, pages=pages,
                           per_page=per_page, total=total, start_no=start_no,
                           start_page=start_page, end_page=end_page,
                           query_base=query_base, sel=sel
                           )
