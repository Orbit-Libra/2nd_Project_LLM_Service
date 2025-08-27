# services/llm_service/db/llm_repository_cx.py
import os, re
import pathlib
from typing import Optional, List, Tuple, Dict, Any
import logging
from .oracle_cx import ConnCtx

from services.llm_service.db.user_schema_loader import load_user_schema, build_select_from_schema, map_row_to_aliases

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

# --- 컬럼명 정규화 ---
_COL_NORM = re.compile(r'[^A-Za-z0-9_]+')
def _norm_col(name: str) -> str:
    # "USER_DATA"."2ND_USR_LPS" → 2ND_USR_LPS
    return _COL_NORM.sub('', (name or '').strip()).upper()

# --- 공용: 단일 행 dict ---
def fetch_one_dict(sql: str, params: dict) -> dict | None:
    """
    단일 행 SELECT 결과를 dict로 반환 (컬럼명 대문자 키, 노멀라이즈 적용)
    """
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        if not row:
            return None
        cols = [_norm_col(d[0]) for d in cur.description]
        return {cols[i]: row[i] for i in range(len(cols))}

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

# --- (신규) user_schema 기반 확장 조회 (미사용 가능) ---
def get_user_traits(user_id: str, schema_path: str) -> Optional[Dict[str, Any]]:
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

# --- (참고용) 스키마 기반 전체 데이터 조회 (현재 체인에선 미사용 가능) ---
def get_full_user_data(usr_id: str) -> Dict[str, Any]:
    """
    user_schema.json 기반으로 사용자의 전체 데이터 조회
    (필요 시 사용. 현재 체인은 자체 로컬 파서를 사용하므로 필수는 아님)
    """
    try:
        schema_path = pathlib.Path(__file__).resolve().parents[1] / "user_schema.json"
        if not schema_path.exists():
            basic_profile = get_user_profile(usr_id)
            if basic_profile:
                return {"name": basic_profile[0], "university": basic_profile[1]}
            return {}

        schema = load_user_schema(str(schema_path))
        sql, _, alias_map = build_select_from_schema(schema)

        with ConnCtx() as conn:
            cur = conn.cursor()
            cur.execute(sql, [usr_id])
            row = cur.fetchone()
            if not row:
                return {}
            result = map_row_to_aliases(row, cur.description, alias_map)
            return result

    except Exception as e:
        log.exception(f"get_full_user_data 실패 (usr_id={usr_id}): {e}")
        try:
            basic_profile = get_user_profile(usr_id)
            if basic_profile:
                return {"name": basic_profile[0], "university": basic_profile[1]}
        except Exception:
            pass
        return {}

# --- 요약 생성 ---
def get_user_academic_summary(usr_id: str) -> Dict[str, Any]:
    try:
        full_data = get_full_user_data(usr_id)
        if not full_data:
            return {}

        summary = {
            "name": full_data.get("name", "미상"),
            "university": full_data.get("university", "미상"),
            "years": {},
            "totals": {
                "total_cps": 0,
                "total_lps": 0,
                "total_vps": 0,
                "active_years": 0
            }
        }

        year_prefixes = ['1ST', '2ND', '3RD', '4TH']
        year_names = ['1학년', '2학년', '3학년', '4학년']

        for i, (prefix, name) in enumerate(zip(year_prefixes, year_names)):
            year_data = {
                "year": full_data.get(f"{prefix}_YR"),
                "cps": full_data.get(f"{prefix}_USR_CPS", 0) or 0,
                "lps": full_data.get(f"{prefix}_USR_LPS", 0) or 0,
                "vps": full_data.get(f"{prefix}_USR_VPS", 0) or 0,
                "score": full_data.get(f"SCR_EST_{['1ST', '2ND', '3RD', '4TH'][i]}", 0) or 0
            }
            summary["years"][name] = year_data
            summary["totals"]["total_cps"] += year_data["cps"]
            summary["totals"]["total_lps"] += year_data["lps"]
            summary["totals"]["total_vps"] += year_data["vps"]
            if year_data["year"]:
                summary["totals"]["active_years"] += 1

        return summary

    except Exception as e:
        log.exception(f"get_user_academic_summary 실패 (usr_id={usr_id}): {e}")
        return {}

def format_user_data_for_llm(usr_id: str, question_type: str = "general") -> str:
    try:
        summary = get_user_academic_summary(usr_id)
        if not summary:
            return ""

        lines = []
        lines.append(f"[{summary['name']}님의 학업 데이터]")
        lines.append(f"소속: {summary['university']}")
        lines.append("")
        lines.append("※ 데이터 설명:")
        lines.append("  - CPS: 자료구입비(원)")
        lines.append("  - LPS: 도서대출건수(건)")
        lines.append("  - VPS: 도서관방문횟수(회)")
        lines.append("")
        for year_name, data in summary["years"].items():
            if data["year"]:
                lines.append(
                    f"{year_name} ({data['year']}년): "
                    f"자료구입비 {data['cps']}원, "
                    f"도서대출 {data['lps']}건, "
                    f"도서관방문 {data['vps']}회"
                )
        if question_type in ["total", "comparison"]:
            lines.append("")
            lines.append("전체 합계:")
            lines.append(f"  - 총 자료구입비: {summary['totals']['total_cps']}원")
            lines.append(f"  - 총 도서대출: {summary['totals']['total_lps']}건")
            lines.append(f"  - 총 도서관방문: {summary['totals']['total_vps']}회")
            lines.append(f"  - 활동 학년 수: {summary['totals']['active_years']}년")
        return "\n".join(lines)

    except Exception as e:
        log.exception(f"format_user_data_for_llm 실패 (usr_id={usr_id}): {e}")
        return ""

def fetch_one(sql: str, params: dict):
    """단일 행을 tuple로 반환 (컬럼명 신뢰하지 않을 때 사용)"""
    with ConnCtx() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()