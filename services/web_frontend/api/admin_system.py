# web_frontend/api/admin_system.py
from flask import Blueprint, jsonify, request, session, abort
import socket

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
    """
    5050, 5100, 5150 포트 열림 여부 반환
    응답 예: {"ports":[{"port":5050,"open":true},{"port":5100,"open":false},{"port":5150,"open":true}]}
    """
    _require_admin()
    ports = [5050, 5100, 5150]
    return jsonify({"ports": [{"port": p, "open": _is_port_open(p)} for p in ports]})

# ─────────────────────────────────────────────────────────────
# 사용자 관리: 목록 조회 / 삭제
# ─────────────────────────────────────────────────────────────
_COLUMNS = ["ID", "USR_CR", "USR_ID", "USR_NAME", "USR_EMAIL", "USR_SNM"]

@admin_system_bp.get("/admin/users")
def list_users():
    """
    USER_DATA 테이블에서 가입 유저 목록 조회
      - 쿼리: ?limit=100 (선택)
    응답 예: { success: true, count: N, columns: [...], rows: [{...}, ...] }
    """
    _require_admin()
    limit = request.args.get("limit", type=int)

    res = get_table_data("USER_DATA", limit=limit)
    if not res.get("success"):
        return jsonify({"success": False, "error": res.get("error", "unknown")}), 500

    rows = []
    for r in res.get("data", []):
        # 🔒 관리자 계정 숨김
        if str(r.get("USR_ID", "")).lower() == "libra_admin":
            continue
        rows.append({k: r.get(k) for k in _COLUMNS})

    # ID 기준 정렬(빈값은 뒤로)
    rows.sort(key=lambda x: (x.get("ID") is None, x.get("ID")))

    return jsonify({
        "success": True,
        "count": len(rows),
        "columns": _COLUMNS,
        "rows": rows
    })

@admin_system_bp.delete("/admin/users/<int:user_id>")
def delete_user(user_id: int):
    """
    USER_DATA 테이블에서 ID 기준으로 삭제
    응답 예: { success: true, deleted: 1, id: 123 }
    - 🔒 관리자 계정(libra_admin)은 삭제 불가
    """
    _require_admin()

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 먼저 해당 ID의 USR_ID 조회
        cur.execute("SELECT USR_ID FROM USER_DATA WHERE ID = :id", {"id": user_id})
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "error": "해당 ID가 존재하지 않습니다."}), 404

        usr_id = (row[0] or "").lower()
        if usr_id == "libra_admin":
            return jsonify({"success": False, "error": "관리자 계정은 삭제할 수 없습니다."}), 403

        # 삭제
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
