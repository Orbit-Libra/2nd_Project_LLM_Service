# services/web_frontend/api/qna_api.py
# 세션의 session['user'](= usr_id)로 권한 제어
# Oracle은 oracle_utils.get_connection()을 씀
# 시퀀스 QNA_POSTS_SEQ, QNA_COMMENTS_SEQ, QNA_FILES_SEQ (초기화 스크립트 기준)
# 계층 댓글은 CONNECT BY로 가져오고, 작성자/관리자만 수정·삭제

import cx_Oracle
from flask import Blueprint, request, jsonify, session
from services.web_frontend.api.oracle_utils import get_connection

# REST API 블루프린트 (/api/qna/...)
bp_qna = Blueprint('bp_qna', __name__, url_prefix='/api/qna')


def _me():
    """로그인한 usr_id (세션 키 'user')."""
    return session.get('user')


def _is_owner_or_admin(conn, table, pk_col, pk_val, usr_id):
    """작성자 본인 또는 관리자(libra_admin)만 허용."""
    if usr_id == 'libra_admin':
        return True
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT USR_ID FROM {table} WHERE {pk_col} = :1", [pk_val])
        row = cur.fetchone()
        return bool(row and row[0] == usr_id)
    finally:
        cur.close()


# -------------------------
# 글 목록 (단순 페이지네이션)
# -------------------------
@bp_qna.get('/posts')
def list_posts():
    page = max(1, int(request.args.get('page', 1)))
    size = max(1, min(50, int(request.args.get('size', 10))))
    off = (page - 1) * size

    conn = cur = cur_cnt = None
    try:
        conn = get_connection()
        cur_cnt = conn.cursor()
        cur_cnt.execute("SELECT COUNT(*) FROM QNA_POSTS")
        total = int(cur_cnt.fetchone()[0])

        cur = conn.cursor()
        # RN 기반 페이징 (목록에 필요한 모든 컬럼 선택)
        cur.execute("""
            SELECT * FROM (
              SELECT
                p.ID, p.USR_ID, p.TITLE,
                p.VIEW_COUNT, p.LIKE_COUNT, p.CREATED_AT,
                p.KIND, p.IS_PUBLIC, p.HAS_FILE, p.AUTHOR_NAME, p.EMAIL,
                ROW_NUMBER() OVER (ORDER BY p.ID DESC) AS RN
              FROM QNA_POSTS p
            )
            WHERE RN BETWEEN :1 AND :2
        """, [off + 1, off + size])

        rows = cur.fetchall()
        items = [{
            'id': r[0], 'usr_id': r[1], 'title': r[2],
            'view_count': int(r[3] or 0), 'like_count': int(r[4] or 0),
            'created_at': r[5].isoformat() if r[5] else None,
            'kind': r[6], 'is_public': bool(r[7]), 'has_file': bool(r[8]),
            'author_name': r[9], 'email': r[10]
        } for r in rows]

        return jsonify(success=True, items=items, total=total, page=page, size=size)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur_cnt: cur_cnt.close()
        if cur: cur.close()
        if conn: conn.close()


# -------------------------
# 글 생성 (신규 필드 포함)
# -------------------------
@bp_qna.post('/posts')
def create_post():
    usr_id = _me()
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    kind = (data.get('kind') or '일반').strip()
    is_pub = 1 if str(data.get('is_public', '1')).lower() in ('1', 'true') else 0
    author_name = (data.get('author_name') or '').strip() or None
    email = (data.get('email') or '').strip() or None

    if not title or not content:
        return jsonify(success=False, error='제목/내용을 입력하세요.'), 400

    conn = cur = cur_seq = None
    try:
        conn = get_connection()
        cur_seq = conn.cursor()
        cur_seq.execute("SELECT QNA_POSTS_SEQ.NEXTVAL FROM DUAL")
        new_id = int(cur_seq.fetchone()[0])

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO QNA_POSTS
                (ID, USR_ID, TITLE, CONTENT, VIEW_COUNT, LIKE_COUNT, CREATED_AT,
                 KIND, IS_PUBLIC, HAS_FILE, AUTHOR_NAME, EMAIL)
            VALUES (:1, :2, :3, :4, 0, 0, SYSDATE, :5, :6, 0, :7, :8)
        """, [new_id, usr_id, title, content, kind, is_pub, author_name, email])
        conn.commit()
        return jsonify(success=True, id=new_id)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur_seq: cur_seq.close()
        if cur: cur.close()
        if conn: conn.close()


# -------------------------
# 글 상세 (+ 댓글 트리 + 첨부)
# -------------------------
@bp_qna.get('/posts/<int:post_id>')
def get_post(post_id: int):
    conn = cur_p = cur_c = cur_f = None
    try:
        conn = get_connection()

        # 글
        cur_p = conn.cursor()
        cur_p.execute("""
            SELECT ID, USR_ID, TITLE, CONTENT, VIEW_COUNT, LIKE_COUNT, CREATED_AT, UPDATED_AT,
                   KIND, IS_PUBLIC, HAS_FILE, AUTHOR_NAME, EMAIL
            FROM QNA_POSTS WHERE ID = :1
        """, [post_id])
        r = cur_p.fetchone()
        if not r:
            return jsonify(success=False, error='글을 찾을 수 없습니다.'), 404

        post = {
            'id': r[0], 'usr_id': r[1], 'title': r[2], 'content': r[3],
            'view_count': int(r[4] or 0), 'like_count': int(r[5] or 0),
            'created_at': r[6].isoformat() if r[6] else None,
            'updated_at': r[7].isoformat() if r[7] else None,
            'kind': r[8], 'is_public': bool(r[9]), 'has_file': bool(r[10]),
            'author_name': r[11], 'email': r[12]
        }

        # 댓글 (계층형)
        cur_c = conn.cursor()
        cur_c.execute("""
            SELECT ID, POST_ID, USR_ID, PARENT_ID, CONTENT, CREATED_AT, LEVEL
            FROM QNA_COMMENTS
            WHERE POST_ID = :1
            START WITH PARENT_ID IS NULL
            CONNECT BY PRIOR ID = PARENT_ID
            ORDER SIBLINGS BY ID
        """, [post_id])
        comments = [{
            'id': c[0], 'post_id': c[1], 'usr_id': c[2],
            'parent_id': c[3], 'content': c[4],
            'created_at': c[5].isoformat() if c[5] else None,
            'level': int(c[6])
        } for c in cur_c.fetchall()]

        # 첨부 목록(conn 닫기 전에!)
        cur_f = conn.cursor()
        cur_f.execute("""
            SELECT ID, ORIG_NAME, STORED_NAME, MIME, FILE_SIZE, PATH
            FROM QNA_FILES
            WHERE POST_ID = :1 ORDER BY ID
        """, [post_id])
        files = [{
            'id': f[0], 'orig_name': f[1], 'stored_name': f[2],
            'mime': f[3], 'size': int(f[4] or 0), 'path': f[5]
        } for f in cur_f.fetchall()]

        return jsonify(success=True, post=post, comments=comments, files=files)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur_p: cur_p.close()
        if cur_c: cur_c.close()
        if cur_f: cur_f.close()
        if conn: conn.close()


# -------------------------
# 글 수정 (작성자/관리자)
# -------------------------
@bp_qna.put('/posts/<int:post_id>')
def update_post(post_id: int):
    usr_id = _me()
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    if not title or not content:
        return jsonify(success=False, error='제목/내용을 입력하세요.'), 400

    conn = cur = None
    try:
        conn = get_connection()
        if not _is_owner_or_admin(conn, 'QNA_POSTS', 'ID', post_id, usr_id):
            return jsonify(success=False, error='권한이 없습니다.'), 403

        cur = conn.cursor()
        cur.execute("""
            UPDATE QNA_POSTS
               SET TITLE = :1,
                   CONTENT = :2,
                   UPDATED_AT = SYSDATE
             WHERE ID = :3
        """, [title, content, post_id])
        conn.commit()
        return jsonify(success=True)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


# -------------------------
# 글 삭제 (작성자/관리자) - 댓글 먼저 제거
# -------------------------
@bp_qna.delete('/posts/<int:post_id>')
def delete_post(post_id: int):
    usr_id = _me()
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    conn = cur = None
    try:
        conn = get_connection()
        if not _is_owner_or_admin(conn, 'QNA_POSTS', 'ID', post_id, usr_id):
            return jsonify(success=False, error='권한이 없습니다.'), 403

        cur = conn.cursor()
        # FK ON DELETE CASCADE가 있어도 안전하게 한 번 더 정리
        cur.execute("DELETE FROM QNA_COMMENTS WHERE POST_ID = :1", [post_id])
        cur.execute("DELETE FROM QNA_POSTS WHERE ID = :1", [post_id])
        conn.commit()
        return jsonify(success=True)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


# -------------------------
# 댓글 작성
# -------------------------
@bp_qna.post('/posts/<int:post_id>/comments')
def create_comment(post_id: int):
    usr_id = _me()
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    parent_id = data.get('parent_id')
    if parent_id in ('', None):
        parent_id = None
    else:
        try:
            parent_id = int(parent_id)
        except Exception:
            parent_id = None

    if not content:
        return jsonify(success=False, error='내용을 입력하세요.'), 400

    conn = cur = cur_seq = cur_chk = None
    try:
        conn = get_connection()

        # 원글 존재 확인
        cur_chk = conn.cursor()
        cur_chk.execute("SELECT 1 FROM QNA_POSTS WHERE ID = :1", [post_id])
        if not cur_chk.fetchone():
            return jsonify(success=False, error='원글이 없습니다.'), 404

        # 시퀀스 발급
        cur_seq = conn.cursor()
        cur_seq.execute("SELECT QNA_COMMENTS_SEQ.NEXTVAL FROM DUAL")
        new_id = int(cur_seq.fetchone()[0])

        # 삽입
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO QNA_COMMENTS (ID, POST_ID, USR_ID, PARENT_ID, CONTENT, CREATED_AT)
            VALUES (:1, :2, :3, :4, :5, SYSDATE)
        """, [new_id, post_id, usr_id, parent_id, content])
        conn.commit()
        return jsonify(success=True, id=new_id)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur_chk: cur_chk.close()
        if cur_seq: cur_seq.close()
        if cur: cur.close()
        if conn: conn.close()


# -------------------------
# 댓글 수정 (작성자/관리자)
# -------------------------
@bp_qna.put('/comments/<int:comment_id>')
def update_comment(comment_id: int):
    usr_id = _me()
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify(success=False, error='내용을 입력하세요.'), 400

    conn = cur = None
    try:
        conn = get_connection()
        if not _is_owner_or_admin(conn, 'QNA_COMMENTS', 'ID', comment_id, usr_id):
            return jsonify(success=False, error='권한이 없습니다.'), 403

        cur = conn.cursor()
        cur.execute("""
            UPDATE QNA_COMMENTS
               SET CONTENT = :1,
                   UPDATED_AT = SYSDATE
             WHERE ID = :2
        """, [content, comment_id])
        conn.commit()
        return jsonify(success=True)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


# -------------------------
# 댓글 삭제 (작성자/관리자) - 자식 대댓글 포함 삭제
# -------------------------
@bp_qna.delete('/comments/<int:comment_id>')
def delete_comment(comment_id: int):
    usr_id = _me()
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    conn = cur = None
    try:
        conn = get_connection()
        if not _is_owner_or_admin(conn, 'QNA_COMMENTS', 'ID', comment_id, usr_id):
            return jsonify(success=False, error='권한이 없습니다.'), 403

        cur = conn.cursor()
        # CONNECT BY로 자신 포함 하위 모두 삭제
        cur.execute("""
            DELETE FROM QNA_COMMENTS
             WHERE ID IN (
               SELECT ID FROM QNA_COMMENTS
               START WITH ID = :1
               CONNECT BY PRIOR ID = PARENT_ID
             )
        """, [comment_id])
        conn.commit()
        return jsonify(success=True)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


# ------------------------
# 좋아요/조회수 증가 API
# ------------------------
@bp_qna.post('/posts/<int:post_id>/view')
def hit_view(post_id):
    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE QNA_POSTS SET VIEW_COUNT = NVL(VIEW_COUNT,0)+1 WHERE ID=:1", [post_id])
        conn.commit()
        return jsonify(success=True)
    finally:
        if cur: cur.close()
        if conn: conn.close()


@bp_qna.post('/posts/<int:post_id>/like')
def hit_like(post_id):
    # 중복 방지(세션 기준, 리스트로 저장)
    liked_list = session.get('liked_posts', [])
    liked = set(liked_list)
    if post_id in liked:
        return jsonify(success=False, error='이미 좋아요를 누르셨습니다.'), 409

    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE QNA_POSTS SET LIKE_COUNT = NVL(LIKE_COUNT,0)+1 WHERE ID=:1", [post_id])
        conn.commit()
        liked.add(post_id)
        session['liked_posts'] = list(liked)  # JSON 직렬화 가능 형태
        return jsonify(success=True)
    finally:
        if cur: cur.close()
        if conn: conn.close()
