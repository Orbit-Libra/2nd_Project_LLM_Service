# services/web_frontend/api/qna_storage.py
# 이 모듈은 템플릿라우트(qna_list.py, qna_detail.py, qna_write.py)가 호출하는 “DAO”
# DB 저장/시드/도우미/댓글/첨부저장 가능

from datetime import datetime
import os
import re
from werkzeug.utils import secure_filename
from flask import session
from services.web_frontend.api.oracle_utils import get_connection

# 업로드 루트
UPLOAD_DIR = os.getenv('QNA_UPLOAD_DIR') or os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------
# 유틸
# -------------------------
def is_valid_email(v: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v or ""))

def mask_name(name: str) -> str:
    """이메일/아이디 등 문자열 첫 글자 + '**' 마스킹"""
    name = (name or "").strip()
    return (name[:1] + "**") if name else "**"

def _author_display(usr_id: str, author_name: str | None) -> str:
    return author_name or mask_name(usr_id)

def _author_from_usrid(usr_id: str) -> str:
    if not usr_id:
        return "**"
    return mask_name(usr_id)

def _status_of_post(conn, post_id: int) -> str:
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT CASE WHEN EXISTS (
                SELECT 1 FROM QNA_COMMENTS c
                 WHERE c.POST_ID = :1 AND c.USR_ID = 'libra_admin'
            ) THEN '답변완료' ELSE '처리중' END
            FROM DUAL
        """, [post_id])
        r = cur.fetchone()
        return r[0] if r else "처리중"
    finally:
        cur.close()

# -------------------------
# 시드: 더이상 메모리 시드 안 함 (호출 호환만 유지)
# -------------------------
def seed_if_empty():
    # DB 버전에서는 아무 것도 안 함 (호환용)
    return

# -------------------------
# 목록 데이터 (템플릿에서 파생필드 포함)
# -------------------------
def items_sorted():
    """
    템플릿(qna_list.py)에서 바로 쓸 수 있는 형태:
    {id, kind, is_public, title, has_file, author, created_at, status}
    """
    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
              p.ID, p.USR_ID, p.TITLE, p.CREATED_AT,
              p.KIND, p.IS_PUBLIC, p.HAS_FILE, p.AUTHOR_NAME,
              CASE WHEN EXISTS (
                SELECT 1 FROM QNA_COMMENTS c
                 WHERE c.POST_ID = p.ID AND c.USR_ID = 'libra_admin'
              ) THEN '답변완료' ELSE '처리중' END AS STATUS
            FROM QNA_POSTS p
            ORDER BY p.ID DESC
        """)
        rows = cur.fetchall()
        out = []
        for r in rows:
            pid, usr_id, title, created_at, kind, is_pub, has_file, author_name, status = r
            out.append({
                "id": int(pid),
                "kind": kind or "일반",
                "is_public": bool(is_pub),
                "title": title,
                "has_file": bool(has_file),
                "author": _author_display(usr_id, author_name),
                "created_at": created_at,  # datetime
                "status": status
            })
        return out
    finally:
        if cur: cur.close()
        if conn: conn.close()

# -------------------------
# 글 단건 조회 (템플릿 detail 용)
# -------------------------
def get_item(qid: int):
    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ID, USR_ID, TITLE, CONTENT, CREATED_AT,
                   KIND, IS_PUBLIC, HAS_FILE, AUTHOR_NAME, EMAIL,
                   VIEW_COUNT, LIKE_COUNT
              FROM QNA_POSTS WHERE ID = :1
        """, [qid])
        r = cur.fetchone()
        if not r:
            return None
        (pid, usr_id, title, content, created_at,
         kind, is_pub, has_file, author_name, email,
         vcnt, lcnt) = r

        status = _status_of_post(conn, pid)

        return {
            "id": int(pid),
            "kind": kind or "일반",
            "is_public": bool(is_pub),
            "title": title,
            "has_file": bool(has_file),
            "author": _author_display(usr_id, author_name),
            "created_at": created_at,
            "status": status,
            "email": email,
            "content": content,
            "view_count": int(vcnt or 0),
            "like_count": int(lcnt or 0),
        }
    finally:
        if cur: cur.close()
        if conn: conn.close()

# -------------------------
# 새 글 ID 시퀀스 (qna_write.py 호환)
# -------------------------
def next_id():
    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT QNA_POSTS_SEQ.NEXTVAL FROM DUAL")
        return int(cur.fetchone()[0])
    finally:
        if cur: cur.close()
        if conn: conn.close()

# -------------------------
# 글 추가 (qna_write.py에서 호출)
# -------------------------
def add_item(item: dict):
    """
    기대 입력:
      { id, title, content, kind, is_public, author_name, email }
    USR_ID는 세션 있으면 세션, 없으면 'guest'
    """
    pid         = int(item.get("id"))
    title       = (item.get("title") or "").strip()
    content     = (item.get("content") or "").strip()
    kind        = (item.get("kind") or "일반").strip()
    is_public   = 1 if str(item.get("is_public", "1")) in ("1","true","True","on") else 0
    author_name = (item.get("author_name") or "").strip() or None
    email       = (item.get("email") or "").strip() or None
    usr_id      = session.get("user") or "guest"  # 로그인 안 한 작성 허용(수정권한은 X)

    if not title or not content:
        raise ValueError("title/content required")

    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO QNA_POSTS (
               ID, USR_ID, TITLE, CONTENT,
               VIEW_COUNT, LIKE_COUNT, CREATED_AT,
               KIND, IS_PUBLIC, HAS_FILE, AUTHOR_NAME, EMAIL
            )
            VALUES (:1, :2, :3, :4, 0, 0, SYSDATE, :5, :6, 0, :7, :8)
        """, [pid, usr_id, title, content, kind, is_public, author_name, email])
        conn.commit()
    finally:
        if cur: cur.close()
        if conn: conn.close()

# -----------------------------
# 파일 저장
# -----------------------------
def save_files(post_id: int, files):
    """
    files: request.files.getlist('files') 로 받은 파일 리스트
    저장: /static/uploads/YYYYMM/ 저장 후 QNA_FILES 레코드 생성
    저장 성공 시 QNA_POSTS.HAS_FILE=1 로 업데이트
    """
    if not files:
        return 0

    ym = datetime.now().strftime("%Y%m")
    dest_dir = os.path.join(UPLOAD_DIR, ym)
    os.makedirs(dest_dir, exist_ok=True)

    saved = 0
    conn = cur_seq = cur = cur_upd = None
    try:
        conn = get_connection()
        for f in files:
            if not f or not getattr(f, 'filename', ''):
                continue
            orig = f.filename
            filename = secure_filename(orig)
            if not filename:
                continue

            stored = datetime.now().strftime("%Y%m%d%H%M%S%f") + "_" + filename
            full_path = os.path.join(dest_dir, stored)
            f.save(full_path)

            size = os.path.getsize(full_path)
            mime = f.mimetype or None
            rel_path = os.path.relpath(
                full_path,
                start=os.path.join(os.path.dirname(__file__), '..')
            )

            if not cur_seq:
                cur_seq = conn.cursor()
            cur_seq.execute("SELECT QNA_FILES_SEQ.NEXTVAL FROM DUAL")
            fid = int(cur_seq.fetchone()[0])

            if not cur:
                cur = conn.cursor()
            cur.execute("""
                INSERT INTO QNA_FILES
                  (ID, POST_ID, ORIG_NAME, STORED_NAME, MIME, FILE_SIZE, PATH, CREATED_AT)
                VALUES (:1, :2, :3, :4, :5, :6, :7, SYSDATE)
            """, [fid, post_id, orig, stored, mime, size, rel_path])
            saved += 1

        if saved:
            cur_upd = conn.cursor()
            cur_upd.execute("UPDATE QNA_POSTS SET HAS_FILE=1 WHERE ID=:1", [post_id])

        conn.commit()
        return saved
    finally:
        if cur_seq: cur_seq.close()
        if cur: cur.close()
        if cur_upd: cur_upd.close()
        if conn: conn.close()

# -------------------------
# 댓글 목록 (템플릿 detail → build_tree 에 넣기 위한 납작 리스트)
# -------------------------
def comments_of(qid: int):
    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ID, PARENT_ID, USR_ID, CONTENT, CREATED_AT
              FROM QNA_COMMENTS
             WHERE POST_ID = :1
             ORDER BY ID
        """, [qid])
        rows = cur.fetchall()
        out = []
        for cid, parent_id, usr_id, content, created_at in rows:
            is_admin = (usr_id == "libra_admin")
            out.append({
                "id": int(cid),
                "parent_id": int(parent_id) if parent_id is not None else None,
                "author": ("관리자" if is_admin else _author_from_usrid(usr_id)),
                "content": content,
                "created_at": created_at,
                "is_admin": bool(is_admin)
            })
        return out
    finally:
        if cur: cur.close()
        if conn: conn.close()

# -------------------------
# 댓글 추가
# -------------------------
def add_comment(qid: int, author: str, content: str, parent_id=None, is_admin=False):
    """
    DB에는 USR_ID만 저장. 세션 있으면 세션, 없으면 'guest'.
    관리자 답변은 세션이 'libra_admin'일 때만 호출됨.
    """
    usr_id = session.get("user") or ("libra_admin" if is_admin else "guest")
    parent_id = int(parent_id) if (isinstance(parent_id, int) or (isinstance(parent_id, str) and parent_id.isdigit())) else None

    conn = cur_seq = cur = None
    try:
        conn = get_connection()
        cur_seq = conn.cursor()
        cur_seq.execute("SELECT QNA_COMMENTS_SEQ.NEXTVAL FROM DUAL")
        new_id = int(cur_seq.fetchone()[0])

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO QNA_COMMENTS (ID, POST_ID, USR_ID, PARENT_ID, CONTENT, CREATED_AT)
            VALUES (:1, :2, :3, :4, :5, SYSDATE)
        """, [new_id, qid, usr_id, parent_id, content])
        conn.commit()
        return new_id
    finally:
        if cur_seq: cur_seq.close()
        if cur: cur.close()
        if conn: conn.close()

# -------------------------
# 트리 구성
# -------------------------
def build_tree(comments):
    kids = {}
    for c in comments:
        kids.setdefault(c["parent_id"], []).append(c)

    def walk(pid=None, depth=0):
        arr = []
        for c in kids.get(pid, []):
            c2 = c.copy()
            c2["depth"] = depth
            arr.append(c2)
            arr.extend(walk(c["id"], depth + 1))
        return arr

    return walk(None, 0)
