#services/web_frontend/api/qna_write.py
#작성 폼/작성/첨부반영 처리(템플릿 라우트)
from flask import render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime
import re
from .qna import qna_bp
from .qna_storage import is_valid_email, add_item, next_id, save_files

#작성 폼
@qna_bp.get("/new")
def qna_new():
    return render_template("qna/question.html")

#작성 처리(서버검증)
@qna_bp.post("/new")
def qna_create():
    title   = (request.form.get("title") or "").strip()
    email   = (request.form.get("email") or "").strip()
    content = (request.form.get("content") or "").strip()
    agree   = request.form.get("agree") == "on"
    kind    = (request.form.get("kind") or "일반").strip()         
    is_pub  = request.form.get("is_public") in ("1","on","true")    
    author_name = (request.form.get("author_name") or "").strip()   
    files = request.files.getlist("files")                          
    
    errors = {}
    if not title: errors["title"] = "제목은 필수입니다."
    if not email or not is_valid_email(email): errors["email"] = "유효한 이메일을 입력하세요."
    if not content or len(content) < 10: errors["content"] = "문의 내용은 10자 이상 입력하세요."
    if not agree: errors["agree"] = "개인정보 수집 및 이용에 동의해주세요."
    if kind not in ("일반","민원"):
        errors["kind"] = "종류를 선택하세요."

    # (선택) XSS 1차 필터: 아주 심플하게 태그 제거 – 필요하면 bleach 도입
    content = re.sub(r"<[^>]+>", "", content)
    
    if errors:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "errors": errors}), 400
        flash("입력값을 확인해주세요.", "error")
        return render_template(
            "qna/question.html",
            form={
                "title": title, "email": email, "content": content,
                "kind": kind, "is_public": "1" if is_pub else "0",
                "author_name": author_name
            },
            errors=errors
        )

    new_id = next_id()
    add_item({
        "id": new_id,
        "kind": kind,
        "is_public": "1" if is_pub else "0",
        "title": title,
        "has_file": False,         # save_files가 이후에 1로 바꿔줌
       "author_name": author_name or None,
        "created_at": datetime.now(),
        "email": email,
        "content": content
    })

    # 첨부 저장(있으면)
    saved = 0
    try:
        saved = save_files(new_id, files)
    except Exception as e:
        print("[WARN] file save failed:", e)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "redirect": url_for("qna.qna_list")})
    return redirect(url_for("qna.qna_list"))
