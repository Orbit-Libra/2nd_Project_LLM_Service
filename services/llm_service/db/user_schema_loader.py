# services/llm_service/db/user_schema_loader.py
import json
import pathlib
from typing import Dict, Tuple, List, Any

def load_user_schema(path: str) -> dict:
    p = pathlib.Path(path).resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    return data

def build_select_from_schema(schema: dict) -> Tuple[str, List[str], Dict[str, str]]:
    """
    USER_DATA 스키마 기반 SELECT 생성
    returns: (sql, bind_names, alias_map)
      - alias_map: {DB_COL -> alias}
    """
    tbl = next((t for t in schema.get("tables", []) if t.get("name") == "USER_DATA"), None)
    if not tbl:
        raise ValueError("USER_DATA table schema not found")
    id_col = tbl.get("id_column", "USR_ID")
    cols_cfg = tbl.get("columns", {}) or {}

    # 기본 안전 컬럼(이름/소속)은 항상 포함
    base_cols = [id_col, "USR_NAME", "USR_SNM"]
    # 스키마에 정의된 컬럼 추가
    select_cols = base_cols + list(cols_cfg.keys())

    # 중복 제거
    seen, uniq = set(), []
    for c in select_cols:
        if c not in seen:
            uniq.append(c)
            seen.add(c)

    cols_sql = ", ".join(uniq)
    sql = f"SELECT {cols_sql} FROM USER_DATA WHERE {id_col} = :1"
    alias_map = {db_col: (cfg.get("alias") or db_col) for db_col, cfg in cols_cfg.items()}
    return sql, [":1"], alias_map

def map_row_to_aliases(row: Tuple[Any, ...], cur_desc, alias_map: Dict[str, str]) -> Dict[str, Any]:
    name_by_idx = {i: d[0] for i, d in enumerate(cur_desc)}  # DB 컬럼명
    out: Dict[str, Any] = {}
    for i, v in enumerate(row):
        db_col = name_by_idx[i]
        out[db_col] = v
        if db_col in alias_map:
            out[alias_map[db_col]] = v
    # 편의 alias
    if "USR_NAME" in out: out.setdefault("name", out["USR_NAME"])
    if "USR_SNM"  in out: out.setdefault("university", out["USR_SNM"])
    return out

def format_profile_text(alias_dict: Dict[str, Any], max_extra: int = 6) -> str:
    """
    사람이 읽을 요약 카드: 이름/소속 + 추가 필드 몇 개만
    """
    parts = []
    nm = str(alias_dict.get("name") or "").strip() or "미상"
    uni = str(alias_dict.get("university") or "").strip() or "미상"
    parts.append(f"이름: {nm}")
    parts.append(f"소속: {uni}")

    exclude = {"name", "university", "USR_NAME", "USR_SNM"}
    extra_keys = [k for k in alias_dict.keys() if k not in exclude]
    shown = 0
    for k in sorted(extra_keys):
        v = alias_dict.get(k)
        if v is None or str(v).strip() == "":
            continue
        parts.append(f"{k}: {v}")
        shown += 1
        if shown >= max_extra:
            break
    return "\n".join(parts)
