#services/web_frontend/api/qna_detail.py
#상세/댓글/관리자 답변

from flask import render_template, redirect, url_for, flash, request, session
from .qna import qna_bp
from .qna_storage import get_item, comments_of, add_comment, build_tree

@qna_bp.get("/<int:qid>")
def qna_detail(qid):
    item = get_item(qid)
    if not item:
        flash("해당 글을 찾을 수 없습니다.", "error")
        return redirect(url_for("qna.qna_list"))
    if not item["is_public"]:
        flash("비공개 글입니다.", "error")
        return redirect(url_for("qna.qna_list"))

    tree = build_tree(comments_of(qid))
    return render_template("qna/detail.html", it=item, comments=tree)

@qna_bp.post("/<int:qid>/comment")
def qna_comment(qid):
    item = get_item(qid)
    if not item or not item["is_public"]:
        flash("댓글을 달 수 없습니다.", "error")
        return redirect(url_for("qna.qna_list"))

    author = (request.form.get("author") or "익명").strip()[:20]
    content = (request.form.get("content") or "").strip()
    parent_id = request.form.get("parent_id")
    parent_id = int(parent_id) if parent_id and parent_id.isdigit() else None

    if len(content) < 2:
        flash("댓글 내용을 2자 이상 입력해주세요.", "error")
        return redirect(url_for("qna.qna_detail", qid=qid))

    add_comment(qid, author, content, parent_id=parent_id, is_admin=False)
    return redirect(url_for("qna.qna_detail", qid=qid) + "#c-end")

@qna_bp.post("/<int:qid>/answer")
def qna_answer(qid):
    if session.get("user") != "libra_admin":
        flash("권한이 없습니다.", "error")
        return redirect(url_for("qna.qna_detail", qid=qid))

    item = get_item(qid)
    if not item:
        flash("글이 존재하지 않습니다.", "error")
        return redirect(url_for("qna.qna_list"))

    content = (request.form.get("content") or "").strip()
    if len(content) < 2:
        flash("답변 내용을 2자 이상 입력해주세요.", "error")
        return redirect(url_for("qna.qna_detail", qid=qid))

    add_comment(qid, "관리자", content, parent_id=None, is_admin=True)
    item["status"] = "답변완료"
    return redirect(url_for("qna.qna_detail", qid=qid) + "#c-end")
