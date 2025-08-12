import sys
import os
import logging
import uuid
from flask import Flask, request, g

# === 로깅 설정 ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s - %(message)s"
)
log = logging.getLogger("data_service")

# 루트 경로 추가 (services/ 상단을 sys.path에 포함)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# 기존 데이터 API
from services.data_service.api.data_api import data_api
from services.data_service.api.num06_api import num06_bp

def create_app():
    app = Flask(__name__)

    # --- 요청 전/후 로깅 훅 ---
    @app.before_request
    def _log_request_start():
        # 요청 ID 생성
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.request_id = rid

        # 요청 바디 프리뷰 (512바이트까지만)
        raw = request.get_data(cache=True) or b""
        preview = raw[:512].decode(errors="ignore")
        body_info = f"len={len(raw)} preview[:512]='{preview}'" if raw else "empty"

        log.info(
            f"[{rid}] -> {request.remote_addr} {request.method} {request.path} "
            f"qs='{request.query_string.decode()}' body({body_info})"
        )

    @app.after_request
    def _log_request_end(resp):
        rid = getattr(g, "request_id", "-")
        try:
            length = resp.calculate_content_length()
        except Exception:
            length = None
        log.info(f"[{rid}] <- {request.method} {request.path} {resp.status_code} length={length}")
        resp.headers["X-Request-ID"] = rid
        return resp

    @app.errorhandler(Exception)
    def _log_unhandled(e):
        rid = getattr(g, "request_id", "-")
        log.exception(f"[{rid}] !! Unhandled error: {e}")
        return {"success": False, "error": "internal_error", "request_id": rid}, 500

    # 블루프린트 등록
    app.register_blueprint(data_api)
    app.register_blueprint(num06_bp)

    return app

app = create_app()

if __name__ == '__main__':
    app.run(port=5050, debug=True, threaded=True)  # threaded=True로 동시 요청 처리
