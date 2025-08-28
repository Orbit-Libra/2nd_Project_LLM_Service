# services/agent_service/tools/oracle_agent_tool/__init__.py
# -*- coding: utf-8 -*-
"""
MCP 툴: 전국 대학(타 대학) 데이터 조회용.
- 입력: 대학명(SNM), 연도(숫자), 메트릭(자연어/라벨)
- 테이블: NUM06_{YEAR}
- 컬럼 추정: mapping 코드 우선 매칭 → 다양한 접미사/패턴 휴리스틱
- 출력: {"ok": True, "result": {...}, "assumed_year": 2024, "debug": {...}}
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import re
import logging

from .db import ConnCtx
from .mapping import normalize_metric_label, code_for_label

log = logging.getLogger("oracle_agent_tool")

# ----- 유틸: 테이블 존재 확인 / 최신년도 -----
def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM ALL_TABLES WHERE TABLE_NAME = :t", {"t": table_name.upper()})
        return cur.fetchone() is not None
    finally:
        cur.close()

def latest_available_year(conn, base: str = "NUM06_", min_year: int = 2014, max_year: int = 2100) -> Optional[int]:
    # 역순 탐색(최신 우선)
    for y in range(min(2100, max_year), min_year-1, -1):
        t = f"{base}{y}"
        if table_exists(conn, t):
            return y
    return None

# ----- 컬럼 후보 생성 휴리스틱 -----
_SUFFIX_PREFERENCE = [
    "", "_SUM", "_TTL", "_TOTAL", "_A", "_B", "_C"
]
# “%_MC%” 같이 패턴 매칭도 지원
def build_candidate_columns(code: str, existing_cols: List[str]) -> List[str]:
    code_u = (code or "").upper()
    if not code_u:
        return []
    candidates: List[str] = []

    # 1) 완전 일치/기본 접미사
    for suf in _SUFFIX_PREFERENCE:
        cand = f"{code_u}{suf}"
        if cand in existing_cols:
            candidates.append(cand)

    # 2) 포함 패턴 (우선순위 낮음)
    if not candidates:
        for c in existing_cols:
            if c == "SNM":
                continue
            if c == code_u or c.endswith("_" + code_u) or c.startswith(code_u + "_") or (code_u in c):
                candidates.append(c)

    # 중복 제거, 순서 보존
    seen, uniq = set(), []
    for c in candidates:
        if c not in seen:
            uniq.append(c); seen.add(c)
    return uniq

# ----- 행/열 조회 -----
def fetch_row_by_university(conn, table: str, university: str) -> Dict[str, Any] | None:
    cur = conn.cursor()
    try:
        sql = f'SELECT * FROM {table} WHERE "SNM" = :snm'
        cur.execute(sql, {"snm": university})
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0].upper() for d in cur.description]
        return {cols[i]: row[i] for i in range(len(cols))}
    finally:
        cur.close()

def list_columns(conn, table: str) -> List[str]:
    cur = conn.cursor()
    try:
        cur.execute(f'SELECT * FROM {table} WHERE ROWNUM = 1')
        return [d[0].upper() for d in cur.description]
    finally:
        cur.close()

# ----- 메인 MCP 함수 -----
def query_university_metric(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload = {
      "university": "서울대학교",       # 필수
      "metric": "자료구입비" | "CPS",   # 필수(자연어/라벨/약어 모두 허용)
      "year": 2023,                     # 선택(없으면 최신 가정)
      "prefer_exact": True              # 선택
    }
    """
    university = (payload.get("university") or "").strip()
    metric_in  = (payload.get("metric") or "").strip()
    year_in    = payload.get("year")
    prefer_exact = bool(payload.get("prefer_exact", True))

    if not university or not metric_in:
        return {"ok": False, "error": "university and metric are required."}

    # 1) 메트릭 라벨 표준화 → 코드
    label = normalize_metric_label(metric_in) or metric_in
    code  = code_for_label(label)
    if not code:
        # 라벨→코드 매핑 실패
        return {"ok": False, "error": f"unknown metric '{metric_in}'", "normalized_label": label}

    with ConnCtx() as conn:
        # 2) 연도/테이블 해결
        if year_in is None:
            y = latest_available_year(conn, base="NUM06_", min_year=2014, max_year=2024)
            assumed_year = y
        else:
            assumed_year = int(year_in)

        table = f'NUM06_{assumed_year}'
        if not table_exists(conn, table):
            return {"ok": False, "error": f"table {table} not found", "assumed_year": assumed_year}

        # 3) 대학 행 조회
        row = fetch_row_by_university(conn, table, university)
        if not row:
            return {"ok": False, "error": f"university '{university}' not found in {table}", "assumed_year": assumed_year}

        cols = list(row.keys())
        cands = build_candidate_columns(code, cols)
        if not cands:
            # 컬럼 후보 없음 → 디버그 반환
            return {
                "ok": False,
                "error": f"no column matches metric code '{code}' in {table}",
                "assumed_year": assumed_year,
                "columns_preview": cols[:40]
            }

        # 4) 값 선택(정확 일치 우선)
        chosen_col = None
        if prefer_exact:
            for suf in [""] + _SUFFIX_PREFERENCE[1:]:
                cc = f"{code}{suf}"
                if cc in cands:
                    chosen_col = cc; break
        if not chosen_col:
            chosen_col = cands[0]

        value = row.get(chosen_col)

        return {
            "ok": True,
            "result": {
                "university": university,
                "year": assumed_year,
                "metric_label": label,
                "metric_code": code,
                "column": chosen_col,
                "value": value
            },
            "assumed_year": assumed_year,
            "debug": {
                "table": table,
                "candidates": cands[:10],
            }
        }

# ---- MCP 등록 헬퍼 (agent_service 내에서 가져다 씀) ----
def register_mcp_tools(registry: Dict[str, Any]) -> None:
    """
    agent_service의 MCP/툴 레지스트리에 등록하는 유틸.
    사용예: registry["oracle.query_university_metric"] = query_university_metric
    """
    registry["oracle.query_university_metric"] = query_university_metric
