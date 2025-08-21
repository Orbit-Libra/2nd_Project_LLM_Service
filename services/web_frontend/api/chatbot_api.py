# services/web_frontend/api/chatbot_api.py
import os
import logging
from flask import Blueprint, request, jsonify, session
import requests

chatbot_bp = Blueprint("chatbot_bp", __name__)
log = logging.getLogger("chatbot_api")

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:5150/generate")  # .env에 명시 권장


@chatbot_bp.post("/api/chat")
def chat_proxy():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    overrides = data.get("overrides") or {}

    if not message:
        return jsonify({"error": "message is required"}), 400

    # 로그인 세션이 있으면 usr_id와 conv_id를 헤더로 전달
    headers = {"Content-Type": "application/json"}
    usr_id = session.get("user")
    if usr_id:
        headers["X-User-Id"] = str(usr_id)

    # conv_id를 세션에 고정해 사용 (없으면 서버가 latest/new를 선택)
    conv_id = session.get("conv_id")
    if conv_id:
        headers["X-Conv-Id"] = str(conv_id)

    try:
        resp = requests.post(
            LLM_API_URL,
            json={"message": message, "overrides": overrides},
            headers=headers,
            timeout=300,
        )
        # LLM 서버 응답을 그대로 전달
        payload = resp.json()

        # 서버가 conv_id를 반환하면 세션에 저장(최초 대화 시작 시)
        try:
            if isinstance(payload, dict) and not session.get("conv_id") and "conv_id" in payload:
                session["conv_id"] = payload["conv_id"]
        except Exception:
            pass

        return jsonify(payload), resp.status_code
    except requests.RequestException as e:
        log.error("[chat_proxy] LLM call failed: %s", e)
        return jsonify({"error": "LLM server unreachable"}), 502
