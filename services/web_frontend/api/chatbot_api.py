from flask import Blueprint, request, jsonify
import requests
import os

chatbot_bp = Blueprint("chatbot_bp", __name__, url_prefix="/api")

LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://127.0.0.1:5150/generate")

@chatbot_bp.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        r = requests.post(LLM_ENDPOINT, json={"message": message}, timeout=120)
        r.raise_for_status()
        payload = r.json()
        return jsonify({"answer": payload.get("answer", "").strip()})
    except requests.RequestException as e:
        return jsonify({"error": f"LLM server error: {e}"}), 502
