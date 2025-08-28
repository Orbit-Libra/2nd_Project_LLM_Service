from flask import Blueprint, jsonify, request, session, abort
import os
import socket
import requests

# Oracle 유틸
from .oracle_utils import get_connection, get_table_data

admin_system_bp = Blueprint("admin_system", __name__)

# ─────────────────────────────────────────────────────────────
# 공통: 관리자 인증
# ─────────────────────────────────────────────────────────────
def _require_admin():
    if session.get("user") != "libra_admin":
        abort(403)

# ─────────────────────────────────────────────────────────────
# 시스템: 포트 상태 확인
# ─────────────────────────────────────────────────────────────
def _is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

@admin_system_bp.get("/admin/ports")
def ports_status():
    _require_admin()
    ports = [5050, 5100, 5150, 5200]
    return jsonify({"ports": [{"port": p, "open": _is_port_open(p)} for p in ports]})

# ─────────────────────────────────────────────────────────────
# 사용자 관리: 목록 조회 / 삭제
# ─────────────────────────────────────────────────────────────
_COLUMNS = ["ID", "USR_CR", "USR_ID", "USR_NAME", "USR_EMAIL", "USR_SNM"]

@admin_system_bp.get("/admin/users")
def list_users():
    _require_admin()
    limit = request.args.get("limit", type=int)

    res = get_table_data("USER_DATA", limit=limit)
    if not res.get("success"):
        return jsonify({"success": False, "error": res.get("error", "unknown")}), 500

    rows = []
    for r in res.get("data", []):
        if str(r.get("USR_ID", "")).lower() == "libra_admin":
            continue
        rows.append({k: r.get(k) for k in _COLUMNS})

    rows.sort(key=lambda x: (x.get("ID") is None, x.get("ID")))
    return jsonify({"success": True, "count": len(rows), "columns": _COLUMNS, "rows": rows})

@admin_system_bp.delete("/admin/users/<int:user_id>")
def delete_user(user_id: int):
    _require_admin()
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT USR_ID FROM USER_DATA WHERE ID = :id", {"id": user_id})
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "해당 ID가 존재하지 않습니다."}), 404

        usr_id = (row[0] or "").lower()
        if usr_id == "libra_admin":
            return jsonify({"success": False, "error": "관리자 계정은 삭제할 수 없습니다."}), 403

        cur.execute("DELETE FROM USER_DATA WHERE ID = :id", {"id": user_id})
        affected = cur.rowcount or 0
        conn.commit()

        return jsonify({"success": True, "deleted": affected, "id": user_id})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        try:
            cur and cur.close()
        finally:
            conn and conn.close()

@admin_system_bp.post("/admin/clear-llm-data")
def clear_llm_data():
    _require_admin()
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM LLM_DATA")
        count_before = cur.fetchone()[0] or 0

        cur.execute("DELETE FROM LLM_DATA")
        deleted_count = cur.rowcount or 0

        conn.commit()

        return jsonify({
            "success": True,
            "message": f"{deleted_count}건의 LLM 대화 데이터가 삭제되었습니다.",
            "deleted": deleted_count,
            "count_before": count_before
        })
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        try:
            cur and cur.close()
        finally:
            conn and conn.close()

@admin_system_bp.post("/admin/llm/reload")
def proxy_llm_reload():
    _require_admin()
    try:
        r = requests.post("http://127.0.0.1:5150/dev/reload", timeout=10)
        return (r.text, r.status_code, {"Content-Type": r.headers.get("Content-Type", "application/json")})
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"proxy error: {e}"}), 502

# ─────────────────────────────────────────────────────────────
# RAG (MCP) 관리: 동기화/초기화/상태 프록시
# ─────────────────────────────────────────────────────────────
def _agent_base_url() -> str:
    return os.getenv("AGENT_SERVICE_URL", "http://127.0.0.1:5200").rstrip("/")

def _agent_post(path: str, payload: dict, timeout: float = 30.0):
    url = f"{_agent_base_url()}{path}"
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    try:
        return resp.json(), resp.status_code
    except ValueError:
        return {"raw": resp.text}, resp.status_code

@admin_system_bp.post("/admin/rag/sync")
def admin_rag_sync():
    """
    프런트가 기대하는 포맷:
      data.stats.indexed_files, data.stats.indexed_chunks
    """
    _require_admin()
    body = request.get_json(silent=True) or {}
    payload = {
        "group": body.get("group") or "DEFAULT",
        "patterns": body.get("patterns") or ["*.pdf", "**/*.pdf"],
        "reset": bool(body.get("reset", False)),
        "force_rebuild": bool(body.get("force_rebuild", False)),
        "limit": int(body.get("limit", 0) or 0),
    }
    if body.get("base_dir"):
        payload["base_dir"] = body["base_dir"]

    try:
        agent, code = _agent_post("/v1/tools/rag/sync", payload, timeout=180.0)

        # pass-through + 안전한 별칭 채움
        result = dict(agent)
        result["success"] = True
        stats = result.get("stats") or {}

        # 레거시 별칭에서 보강
        if "indexed_files" not in stats and "files" in result:
            stats["indexed_files"] = int(result.get("files") or 0)
        if "indexed_chunks" not in stats and "chunks" in result:
            stats["indexed_chunks"] = int(result.get("chunks") or 0)

        # 완성된 stats 보장
        result["stats"] = stats
        return jsonify(result), code
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"rag sync proxy error: {e}"}), 502

@admin_system_bp.post("/admin/rag/reset")
def admin_rag_reset():
    _require_admin()
    body = request.get_json(silent=True) or {}
    payload = {"group": body.get("group") or "DEFAULT"}
    try:
        agent, code = _agent_post("/v1/tools/rag/reset", payload, timeout=60.0)
        result = dict(agent)
        result["success"] = True
        return jsonify(result), code
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"rag reset proxy error: {e}"}), 502

@admin_system_bp.get("/admin/rag/status")
def admin_rag_status():
    _require_admin()
    group = request.args.get("group") or "DEFAULT"
    try:
        agent, code = _agent_post("/v1/tools/rag/status", {"group": group}, timeout=20.0)
        result = dict(agent)
        result["success"] = True
        return jsonify(result), code
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"rag status proxy error: {e}"}), 502
