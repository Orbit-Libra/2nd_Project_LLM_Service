import os, logging, requests
from flask import Blueprint, jsonify, request

rag_bp = Blueprint("rag_api", __name__)
log = logging.getLogger("rag_api")

AGENT_URL = os.getenv("AGENT_SERVICE_URL", "http://127.0.0.1:5200")

@rag_bp.post("/admin/rag/sync")
def admin_rag_sync():
    try:
        payload = request.get_json(silent=True) or {"reset": True}
        r = requests.post(f"{AGENT_URL}/v1/tools/rag/sync", json=payload, timeout=60)
        if r.status_code != 200:
            return jsonify({"success": False, "error": r.text}), r.status_code
        return jsonify(r.json())
    except Exception as e:
        log.exception("admin_rag_sync error: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500

@rag_bp.post("/admin/rag/reset")
def admin_rag_reset():
    try:
        r = requests.post(f"{AGENT_URL}/v1/tools/rag/reset", timeout=60)
        if r.status_code != 200:
            return jsonify({"success": False, "error": r.text}), r.status_code
        return jsonify(r.json())
    except Exception as e:
        log.exception("admin_rag_reset error: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500
