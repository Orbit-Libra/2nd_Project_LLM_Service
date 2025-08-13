import os, time, json, sys
import logging, uuid
from flask import Flask, request, jsonify, g
from dotenv import load_dotenv

# === 경로/환경 설정 ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../prediction_service
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))               # .../services
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH, override=True)

# sys.path 보정
for p in [PROJECT_ROOT, BASE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core_utiles.OracleDBConnection import OracleDBConnection
from Predictor.PickleLoader import PickleLoader
from Predictor.TableBuilder_User import TableBuilderUser

# === 로깅 설정 ===
logging.basicConfig(
    level=logging.INFO,  # 필요시 DEBUG
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s - %(message)s"
)
log = logging.getLogger("predict")
werklog = logging.getLogger("werkzeug")
werklog.setLevel(logging.INFO)

app = Flask(__name__)

# 전역 모델 캐시 (읽기 전용 사용)
_MODEL_BUNDLE = {}

def get_model_bundle():
    """모델/설정 번들을 1회 로드 후 캐시."""
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE:
        return _MODEL_BUNDLE
    cfg_name = os.getenv("MODEL_CONFIG_NAME", "Num01_Config_XGB.json")
    cfg_path = os.path.join(PROJECT_ROOT, "ml_service", "_Configs", cfg_name)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    models = PickleLoader(cfg).load()
    _MODEL_BUNDLE = {"config": cfg, "models": models}
    log.info(f"Model bundle loaded: {cfg_name}")
    return _MODEL_BUNDLE

# === 요청 로깅 훅 ===
@app.before_request
def _log_request_start():
    # 외부에서 X-Request-ID를 주면 사용, 없으면 생성
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    g.request_id = rid

    # 바디는 개인정보 우려로 전체 미출력: 앞부분 프리뷰 또는 길이만
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
    return jsonify(success=False, error="internal_error", request_id=rid), 500

# === 헬스체크 ===
@app.get("/healthz")
def healthz():
    return jsonify(ok=True)

# === 예측 API ===
@app.post("/predict/user")
def predict_user():
    """
    요청 JSON: USR_SNM + 각 학년(YR/CPS/LPS/VPS)
    응답 JSON: SCR_EST_1ST~4TH
    """
    rid = getattr(g, "request_id", "-")
    t0 = time.time()
    payload = request.get_json(silent=True) or {}

    # 민감 데이터 로그 최소화: 키만 출력
    log.info(f"[{rid}] predict start payload_keys={list(payload.keys())}")

    try:
        bundle = get_model_bundle()

        db = OracleDBConnection()
        db.connect()
        try:
            tb = TableBuilderUser(
                config=bundle["config"],
                conn=db.conn,
                engine=db.engine,
                models=bundle["models"]
            )
            preds = tb.predict_from_payload(payload)
        finally:
            db.close()

        ms = int((time.time() - t0) * 1000)
        log.info(f"[{rid}] predict ok elapsed_ms={ms}")
        return jsonify(success=True, predictions=preds, elapsed_ms=ms)

    except Exception as e:
        # 스택트레이스 포함
        log.exception(f"[{rid}] predict failed: {e}")
        return jsonify(success=False, error=str(e), request_id=rid), 400

# === 개발 실행 ===
if __name__ == "__main__":
    port = int(os.getenv("PREDICT_API_PORT", "5100"))
    # 멀티스레드 테스트가 필요하면 threaded=True 권장
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
