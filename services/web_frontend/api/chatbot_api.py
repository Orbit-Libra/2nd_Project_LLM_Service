from flask import Blueprint, request, jsonify
import requests, os, logging

chatbot_bp = Blueprint("chatbot_bp", __name__, url_prefix="/api")
log = logging.getLogger("chatbot")

LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://127.0.0.1:5150/generate")

@chatbot_bp.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        # timeout 파라미터 제거 → 무제한 대기
        r = requests.post(LLM_ENDPOINT, json={"message": message})
    except requests.exceptions.RequestException as e:
        log.exception("LLM connection error")
        return jsonify({"error": f"LLM connection error: {e}"}), 502

    if r.status_code != 200:
        log.error("LLM bad response %s: %s", r.status_code, r.text[:400])
        return jsonify({"error": "LLM upstream error", "detail": r.text[:400]}), 502

    try:
        payload = r.json()
    except ValueError:
        log.error("LLM returned non-JSON: %s", r.text[:400])
        return jsonify({"error": "LLM returned invalid JSON"}), 502

    return jsonify({"answer": (payload.get("answer") or "").strip()})
