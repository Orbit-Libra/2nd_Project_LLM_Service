import os
import pathlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from services.llm_service.model.router import ModelRouter
from services.llm_service.model.config_loader import load_config

_ROUTER = None

def create_app():
    app = Flask(__name__)

    # .env 로드
    env_path = pathlib.Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))

    # 컨피그 로드 + 라우터 준비
    global _ROUTER
    if _ROUTER is None:
        cfg_path = os.getenv("MODEL_CONFIG")
        if not cfg_path:
            raise RuntimeError("MODEL_CONFIG is not set in .env")
        cfg = load_config(cfg_path, os.environ)
        _ROUTER = ModelRouter.from_config(cfg, os.environ)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "backend": _ROUTER.backend_name,
            "model": _ROUTER.model_name,
        }

    @app.post("/generate")
    def generate():
        """
        Body 예:
        {
          "message": "질문",
          "overrides": { "temperature": 0.5, "max_new_tokens": 256 }  # (옵션)
        }
        """
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        overrides = data.get("overrides") or {}
        if not message:
            return jsonify({"error": "message is required"}), 400

        try:
            answer = _ROUTER.generate(user_text=message, overrides=overrides)
            return jsonify({"message": message, "answer": answer})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5150, debug=False, use_reloader=False, threaded=True)
