# services/llm_service/db/llm_repository_cx.py
from typing import Optional, List, Tuple, Dict, Any
import logging
from .oracle_cx import ConnCtx

log = logging.getLogger("llm_repo")

def _as_text(v) -> str:
    """CLOB(LOB) → str 안전 변환 헬퍼"""
    if v is None:
        return ""
    read = getattr(v, "read", None)
    if callable(read):
        try:
            return read()
        except Exception:
            return str(v)
    return v if isinstance(v, str) else str(v)

# --- 유저 프로필 (USER_DATA) ---
def get_user_profile(user_id: str) -> Optional[Tuple[str, str]]:
    sql = "SELECT USR_NAME, USR_SNM FROM USER_DATA WHERE USR_ID = :1"
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute(sql, [user_id])
        row = cur.fetchone()
        if not row:
            return None
        return (_as_text(row[0]), _as_text(row[1]))

# --- (신규) user_schema 기반 확장 조회 ---
def get_user_traits(user_id: str, schema_path: str) -> Optional[Dict[str, Any]]:
    from .user_schema_loader import load_user_schema, build_select_from_schema, map_row_to_aliases
    schema = load_user_schema(schema_path)
    sql, _, alias_map = build_select_from_schema(schema)
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute(sql, [user_id])
        row = cur.fetchone()
        if not row:
            return None
        alias_dict = map_row_to_aliases(row, cur.description, alias_map)
        # LOB 안전 변환
        for k, v in list(alias_dict.items()):
            alias_dict[k] = _as_text(v)
        return alias_dict

# --- 시퀀스 ---
def next_conv_id() -> int:
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT SEQ_LLM_CONV.NEXTVAL FROM dual")
        return int(cur.fetchone()[0])

def next_msg_id() -> int:
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT SEQ_LLM_MSG.NEXTVAL FROM dual")
        return int(cur.fetchone()[0])

# --- 대화/메시지 ---
def latest_conv_id(user_id: str) -> Optional[int]:
    log = logging.getLogger("llm_repo")
    log.info("latest_conv_id called (user_id=%r)", user_id)
    sql = """
        SELECT conv_id
          FROM (
            SELECT conv_id, MAX(msg_id) AS mx
              FROM llm_data
             WHERE usr_id = :1
             GROUP BY conv_id
             ORDER BY mx DESC
          )
         WHERE ROWNUM = 1
    """
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute(sql, [user_id])
        r = cur.fetchone()
        return int(r[0]) if r else None

def append_message(conv_id: int, user_id: str, role: str, content: str, tokens: int = 0) -> int:
    mid = next_msg_id()
    sql = """
      INSERT INTO llm_data (conv_id, usr_id, msg_id, role, content, tokens, created_at)
      VALUES (:1, :2, :3, :4, :5, :6, SYSTIMESTAMP)
    """
    with ConnCtx() as conn:
        cur = conn.cursor()
        try:
            import oracledb
            cur.setinputsizes(None, None, None, None, oracledb.DB_TYPE_CLOB, None)
        except Exception:
            try:
                import cx_Oracle
                cur.setinputsizes(None, None, None, None, cx_Oracle.CLOB, None)
            except Exception:
                pass
        cur.execute(sql, [int(conv_id), str(user_id), int(mid), str(role), str(content), int(tokens)])
    return mid

def fetch_history(conv_id: int, limit: int = 12) -> List[Dict[str, Any]]:
    sql = """
      SELECT role, content FROM (
        SELECT role, content, msg_id
          FROM llm_data
         WHERE conv_id = :1
         ORDER BY msg_id DESC
      )
      WHERE ROWNUM <= :2
      ORDER BY msg_id ASC
    """
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute(sql, [conv_id, limit])
        rows = cur.fetchall()
        return [{"role": r[0], "content": _as_text(r[1])} for r in rows]

def max_msg_id(conv_id: int) -> int:
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute("SELECT NVL(MAX(msg_id), 0) FROM llm_data WHERE conv_id = :1", [conv_id])
        return int(cur.fetchone()[0])

# --- 요약 관리 ---
def get_latest_summary(conv_id: int) -> Optional[Tuple[str, int]]:
    sql = """
      SELECT summary, summary_up_to_msg_id FROM (
        SELECT summary, summary_up_to_msg_id, msg_id
          FROM llm_data
         WHERE conv_id = :1
           AND summary IS NOT NULL
         ORDER BY msg_id DESC
      )
      WHERE ROWNUM = 1
    """
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute(sql, [conv_id])
        r = cur.fetchone()
        if not r:
            return None
        return (_as_text(r[0]), int(r[1]))

def upsert_summary_on_latest_row(conv_id: int, summary_text: str, cover_to_msg_id: int) -> None:
    sql = """
      UPDATE llm_data
         SET summary = :1, summary_up_to_msg_id = :2
       WHERE conv_id = :3
         AND msg_id = (SELECT MAX(msg_id) FROM llm_data WHERE conv_id = :3)
    """
    with ConnCtx() as conn:
        cur = conn.cursor()
        try:
            import oracledb
            cur.setinputsizes(oracledb.DB_TYPE_CLOB, None, None)
        except Exception:
            try:
                import cx_Oracle
                cur.setinputsizes(cx_Oracle.CLOB, None, None)
            except Exception:
                pass
        cur.execute(sql, [summary_text, int(cover_to_msg_id), int(conv_id)])
