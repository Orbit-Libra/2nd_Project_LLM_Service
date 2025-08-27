# services/llm_service/api/server.py
import os
import pathlib
import logging
import importlib
import sys
from flask import Flask, jsonify
from dotenv import load_dotenv

from services.llm_service.model.router import ModelRouter
from services.llm_service.model.config_loader import load_config

_ROUTER = None
_CFG = None
_API_MODULE = None
_API_MODULE_PATH = "services.llm_service.api.llm_api"

log = logging.getLogger("llm_server")
logging.basicConfig(
    level=getattr(logging, os.getenv("APP_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)


def create_app():
    """
    Flask 앱 생성 및 모델 로딩 (Hot Reload 지원)
    """
    app = Flask(__name__)

    log.info("=== LLM 서버 초기화 시작 ===")

    # === .env 로드 ===
    env_path = pathlib.Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=str(env_path))
        log.info("환경변수 로드 완료: %s", env_path)

    # === Oracle Client PATH (옵션) ===
    ic_path = (os.getenv("ORACLE_CLIENT_PATH") or "").strip()
    if ic_path and ic_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ic_path + os.pathsep + os.environ.get("PATH", "")
        log.info("Oracle Client PATH 추가: %s", ic_path)

    # === 모델 로딩 (한 번만) ===
    global _ROUTER, _CFG
    if _ROUTER is None:
        log.info("설정 파일 로드 중...")
        _CFG = load_config(os.environ)

        log.info("모델 라우터 초기화 중... (오픈비노 NPU 스냅샷 로딩)")
        _ROUTER = ModelRouter.from_config(_CFG, os.environ)

        log.info("모델 로딩 완료!")
        log.info("- Backend: %s", _ROUTER.backend_name)
        log.info("- Model: %s", _ROUTER.model_name)
    else:
        log.info("기존 모델 라우터 재사용")
    
    # --- 서비스별 로거 레벨 튜닝 ---
    logging.getLogger("orchestrator").setLevel(logging.INFO)
    logging.getLogger("orchestrator.intent").setLevel(logging.INFO)
    logging.getLogger("user_data_chain").setLevel(
        getattr(logging, os.getenv("USER_DATA_CHAIN_LOG_LEVEL", "WARNING").upper(), logging.WARNING)
    )

    # === 모듈 리로드 유틸 ===
    def reload_api_routes():
        """API 모듈을 동적으로 리로드"""
        global _API_MODULE
        try:
            modules_to_reload = [
                "services.llm_service.chains.user_data_chain",
                "services.llm_service.db.llm_repository_cx",
                "services.llm_service.orchestrator",
                "services.llm_service.orchestrator.intent_classifier",
                "services.llm_service.orchestrator.tool_hints",
                "services.llm_service.orchestrator.planner",
                "services.llm_service.orchestrator.agent_client",
                _API_MODULE_PATH
            ]
            for module_name in modules_to_reload:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                    log.info("모듈 리로드: %s", module_name)

            if _API_MODULE is None:
                _API_MODULE = importlib.import_module(_API_MODULE_PATH)
                log.info("API 모듈 최초 로드: %s", _API_MODULE_PATH)
            else:
                _API_MODULE = importlib.reload(_API_MODULE)
                log.info("API 모듈 리로드 완료: %s", _API_MODULE_PATH)

            return _API_MODULE
        except Exception as e:
            log.error("API 모듈 로드/리로드 실패: %s", e)
            return None

    # === API 라우트 최초 등록 ===
    api_module = reload_api_routes()
    if api_module:
        handlers = api_module.build_handlers(app, _ROUTER, _CFG)
        api_module.register_routes_once(app, handlers)
    else:
        log.error("API 모듈 로드 실패 - 서버 시작 불가")
        return None

    # === 개발용 정보 엔드포인트 ===
    @app.route("/dev/info")
    def dev_info():
        """개발용: 현재 상태 정보"""
        api_file_path = pathlib.Path(__file__).parent / "llm_api.py"
        chain_file_path = pathlib.Path(__file__).parent.parent / "chains" / "user_data_chain.py"

        api_mtime = api_file_path.stat().st_mtime if api_file_path.exists() else 0
        chain_mtime = chain_file_path.stat().st_mtime if chain_file_path.exists() else 0

        return jsonify({
            "model_loaded": _ROUTER is not None,
            "model_backend": _ROUTER.backend_name if _ROUTER else None,
            "api_module_path": _API_MODULE_PATH,
            "api_file_mtime": api_mtime,
            "chain_file_mtime": chain_mtime,
            "dev_mode": (os.getenv("DEV_MODE", "false").lower() == "true"),
            "langchain_enabled": True,
            "pid": os.getpid()
        })

    # === 개발용 리로드 엔드포인트 ===
    @app.route("/dev/reload", methods=["POST"])
    def dev_reload():
        try:
            global _CFG
            # 최신 설정 다시 로드
            _CFG = load_config(os.environ)

            api_module_latest = reload_api_routes()
            if not api_module_latest:
                return jsonify({"status": "error", "message": "리로드 실패"}), 500

            new_handlers = api_module_latest.build_handlers(app, _ROUTER, _CFG)
            api_module_latest.rebind_handlers(app, new_handlers)

            return jsonify({
                "status": "success",
                "message": "API 로직 & 설정 핫 리로드 완료",
                "timestamp": __import__("time").time(),
                "langchain_enabled": True
            })
        except Exception as e:
            log.exception("리로드 실패: %s", e)
            return jsonify({"status": "error", "message": str(e)}), 500

    log.info("=== LLM 서버 초기화 완료 (랭체인 통합) ===")
    return app


if __name__ == "__main__":
    app = create_app()
    if app:
        dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
        app.run(
            host="0.0.0.0",
            port=5150,
            debug=dev_mode,
            use_reloader=False,  # 수동 리로드 사용
            threaded=True
        )
    else:
        log.error("앱 생성 실패")
