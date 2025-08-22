#services/web_frontend/api/qna_write.py
#작성 폼/작성 처리
from flask import render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime
from .qna import qna_bp
from .qna_storage import is_valid_email, mask_name, add_item, next_id

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

    errors = {}
    if not title: errors["title"] = "제목은 필수입니다."
    if not email or not is_valid_email(email): errors["email"] = "유효한 이메일을 입력하세요."
    if not content or len(content) < 10: errors["content"] = "문의 내용은 10자 이상 입력하세요."
    if not agree: errors["agree"] = "개인정보 수집 및 이용에 동의해주세요."

    if errors:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False, "errors": errors}), 400
        flash("입력값을 확인해주세요.", "error")
        return render_template("qna/question.html",
                               form={"title": title, "email": email, "content": content},
                               errors=errors)

    new_id = next_id()
    add_item({
        "id": new_id,
        "kind": "일반",
        "is_public": True,
        "title": title,
        "has_file": False,
        "author": mask_name(email.split("@")[0]),
        "created_at": datetime.now(),
        "status": "처리중",
        "email": email,
        "content": content
    })

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "redirect": url_for("qna.qna_list")})
    return redirect(url_for("qna.qna_list"))
