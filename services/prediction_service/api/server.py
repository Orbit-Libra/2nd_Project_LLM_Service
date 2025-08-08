import os, time, json
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # .../prediction_service
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))               # .../services
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH, override=True)

# path 보정
for p in [PROJECT_ROOT, BASE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from core_utiles.OracleDBConnection import OracleDBConnection
from Predictor.PickleLoader import PickleLoader
from Predictor.TableBuilder_User import TableBuilderUser

app = Flask(__name__)

# 전역 모델 캐시
_MODEL_BUNDLE = {}

def get_model_bundle():
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE:
        return _MODEL_BUNDLE
    cfg_name = os.getenv("MODEL_CONFIG_NAME", "Num01_Config_XGB.json")
    cfg_path = os.path.join(PROJECT_ROOT, "ml_service", "_Configs", cfg_name)
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    models = PickleLoader(cfg).load()
    _MODEL_BUNDLE = {"config": cfg, "models": models}
    return _MODEL_BUNDLE

@app.get("/healthz")
def healthz():
    return jsonify(ok=True)

@app.post("/predict/user")
def predict_user():
    """
    요청 JSON: USR_SNM + 각 학년(YR/CPS/LPS/VPS)
    응답 JSON: SCR_EST_1ST~4TH
    """
    payload = request.get_json(silent=True) or {}
    t0 = time.time()
    try:
        bundle = get_model_bundle()
        db = OracleDBConnection()
        db.connect()
        try:
            tb = TableBuilderUser(config=bundle["config"], conn=db.conn, engine=db.engine, models=bundle["models"])
            preds = tb.predict_from_payload(payload)
        finally:
            db.close()

        return jsonify(success=True, predictions=preds, elapsed_ms=int((time.time()-t0)*1000))
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

if __name__ == "__main__":
    port = int(os.getenv("PREDICT_API_PORT", "5100"))
    app.run(host="0.0.0.0", port=port, debug=True)
