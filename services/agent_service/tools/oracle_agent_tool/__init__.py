# -*- coding: utf-8 -*-
"""
MCP 툴: 전국 대학 데이터 조회
등록 키:
- oracle_agent_tool.query_university_metric  (NUM06_YYYY)
- oracle_agent_tool.query_estimation_score   (ESTIMATIONFUTURE.SCR_EST_YYYY)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging, re

try:
    from .db import ConnCtx
    from .mapping import normalize_metric_label, code_for_label
except ImportError as e:
    logging.error("Oracle tool dependencies not available: %s", e)
    ConnCtx = None

log = logging.getLogger("oracle_agent_tool")

# --- 공통 유틸 ---
def _table_exists(conn, table_name: str) -> bool:
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM ALL_TABLES WHERE TABLE_NAME = :t", {"t": table_name.upper()})
        return cur.fetchone() is not None
    finally:
        cur.close()

def _latest_year(conn, base: str = "NUM06_", min_year: int = 2014, max_year: int = 2100) -> Optional[int]:
    if not conn:
        return None
    for y in range(min(2100, max_year), min_year-1, -1):
        if _table_exists(conn, f"{base}{y}"):
            return y
    return None

def _fetch_row_by_snm(conn, table: str, snm: str) -> Dict[str, Any] | None:
    if not conn:
        return None
    cur = conn.cursor()
    try:
        sql = f'SELECT * FROM {table} WHERE "SNM" = :snm'
        cur.execute(sql, {"snm": snm})
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0].upper() for d in cur.description]
        return {cols[i]: row[i] for i in range(len(cols))}
    finally:
        cur.close()

# --- 1) 일반 메트릭(NUM06_YYYY) ---
_SUFFIX_PREF = ["", "_SUM", "_TTL", "_TOTAL", "_A", "_B", "_C"]

def _candidate_cols(code: str, cols: List[str]) -> List[str]:
    code_u = (code or "").upper()
    cands = []
    for suf in _SUFFIX_PREF:
        cand = f"{code_u}{suf}"
        if cand in cols: cands.append(cand)
    if not cands:
        for c in cols:
            if c != "SNM" and (c == code_u or c.endswith("_"+code_u) or c.startswith(code_u+"_") or code_u in c):
                cands.append(c)
    # uniq
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            out.append(c); seen.add(c)
    return out

def query_university_metric(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    args: { university, metric, year?, prefer_exact? }
    """
    if ConnCtx is None:
        log.error("Oracle connection not available")
        return {"ok": False, "error": "Oracle connection not available"}
    
    univ = (payload.get("university") or "").strip()
    metric_in = (payload.get("metric") or "").strip()
    year = payload.get("year")
    prefer_exact = bool(payload.get("prefer_exact", True))
    
    log.info("[ORACLE] query_university_metric called: univ=%s, metric=%s, year=%s", univ, metric_in, year)
    
    if not univ or not metric_in:
        return {"ok": False, "error": "university and metric are required."}

    try:
        label = normalize_metric_label(metric_in) or metric_in
        code = code_for_label(label)
        if not code:
            return {"ok": False, "error": f"unknown metric '{metric_in}'", "normalized_label": label}

        with ConnCtx() as conn:
            if year is None:
                year = _latest_year(conn, base="NUM06_", min_year=2014, max_year=2024)

            table = f"NUM06_{int(year)}"
            if not _table_exists(conn, table):
                return {"ok": False, "error": f"table {table} not found", "assumed_year": year}

            row = _fetch_row_by_snm(conn, table, univ)
            if not row:
                return {"ok": False, "error": f"university '{univ}' not found in {table}", "assumed_year": year}

            cols = list(row.keys())
            cands = _candidate_cols(code, cols)
            if not cands:
                return {"ok": False, "error": f"no column for code '{code}' in {table}", "assumed_year": year, "columns_preview": cols[:40]}

            chosen = None
            if prefer_exact:
                for suf in [""] + _SUFFIX_PREF[1:]:
                    if f"{code}{suf}" in cands:
                        chosen = f"{code}{suf}"; break
            if not chosen:
                chosen = cands[0]

            result = {
                "ok": True,
                "result": {
                    "university": univ,
                    "year": int(year),
                    "metric_label": label,
                    "metric_code": code,
                    "column": chosen,
                    "value": row.get(chosen)
                },
                "assumed_year": int(year),
                "debug": {"table": table, "candidates": cands[:10]}
            }
            log.info("[ORACLE] query_university_metric success: %s", result["result"])
            return result
            
    except Exception as e:
        log.exception("[ORACLE] query_university_metric error: %s", e)
        return {"ok": False, "error": str(e)}

# --- 2) 예측점수(ESTIMATIONFUTURE.SCR_EST_YYYY) ---
def query_estimation_score(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    args: { university, year? }  # year 없으면 근사(최신 가정 또는 가장 가까운 열)
    """
    if ConnCtx is None:
        log.error("Oracle connection not available")
        return {"ok": False, "error": "Oracle connection not available"}
    
    univ = (payload.get("university") or "").strip()
    year = payload.get("year")
    
    log.info("[ORACLE] query_estimation_score called: univ=%s, year=%s", univ, year)
    
    if not univ:
        return {"ok": False, "error": "university is required."}

    try:
        target_year = int(year) if year else 2026  # 상한 가정, 필요시 조정
        col = f"SCR_EST_{target_year}"

        with ConnCtx() as conn:
            if not _table_exists(conn, "ESTIMATIONFUTURE"):
                return {"ok": False, "error": "table ESTIMATIONFUTURE not found"}

            row = _fetch_row_by_snm(conn, "ESTIMATIONFUTURE", univ)
            if not row:
                return {"ok": False, "error": f"university '{univ}' not found in ESTIMATIONFUTURE"}

            if col not in row:
                # 가장 가까운 연도 선택
                est_cols = [k for k in row.keys() if k.startswith("SCR_EST_")]
                years = []
                for c in est_cols:
                    try:
                        years.append(int(c.rsplit("_",1)[1]))
                    except Exception:
                        pass
                if not years:
                    return {"ok": False, "error": "no SCR_EST_* columns present"}
                tgt = min(years, key=lambda y: abs(y - target_year))
                col = f"SCR_EST_{tgt}"

            result = {
                "ok": True,
                "result": {
                    "university": univ,
                    "year": int(re.findall(r"\d{4}", col)[0]),
                    "metric_label": "예측점수",
                    "metric_code": "SCR_EST",
                    "column": col,
                    "value": row.get(col)
                },
                "debug": {"table": "ESTIMATIONFUTURE"}
            }
            log.info("[ORACLE] query_estimation_score success: %s", result["result"])
            return result
            
    except Exception as e:
        log.exception("[ORACLE] query_estimation_score error: %s", e)
        return {"ok": False, "error": str(e)}

def register_mcp_tools(registry: Dict[str, Any], _cfg: Dict[str, Any] | None = None) -> None:
    log.info("[ORACLE] Registering MCP tools")
    registry["oracle_agent_tool.query_university_metric"] = query_university_metric
    registry["oracle_agent_tool.query_estimation_score"]  = query_estimation_score
    log.info("[ORACLE] MCP tools registered: %s", ["oracle_agent_tool.query_university_metric", "oracle_agent_tool.query_estimation_score"])