# services/web_frontend/api/chatbot_api.py
import os
import logging
from flask import Blueprint, request, jsonify, session
import requests

chatbot_bp = Blueprint("chatbot_bp", __name__)
log = logging.getLogger("chatbot_api")

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:5150/generate")

# 호환용 alias
@chatbot_bp.route("/api/chat", methods=["POST"])
@chatbot_bp.route("/api/generate", methods=["POST"])
@chatbot_bp.route("/generate", methods=["POST"])
def chat_proxy():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    overrides = data.get("overrides") or {}
    if not message:
        return jsonify({"error": "message is required"}), 400

    headers = {"Content-Type": "application/json"}

    # 로그인 유저라면 세션 usr_id 전달
    usr_id = session.get("user")
    if usr_id:
        headers["X-User-Id"] = str(usr_id)

    # 세션 기준 "첫 호출"이면 명시적으로 플래그 전달
    # (세션에 conv_id가 아직 없으면 첫 턴)
    if not session.get("conv_id"):
        headers["X-First-Turn"] = "1"
        # body override도 함께(양쪽 다 지원)
        overrides = {**overrides, "first_turn": True}

    # conv_id가 이미 있으면 함께 전달(선택 사항)
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
        # 그대로 전달
        payload = resp.json()

        # 응답에 conv_id 있으면 세션에 저장 → 이후부턴 첫 턴 아님
        try:
            if isinstance(payload, dict) and "conv_id" in payload:
                session["conv_id"] = payload["conv_id"]
        except Exception:
            pass

        return jsonify(payload), resp.status_code
    except requests.RequestException as e:
        log.error("[chat_proxy] LLM call failed: %s", e)
        return jsonify({"error": "LLM server unreachable"}), 502
