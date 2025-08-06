import joblib

def save_model(model, path: str):
    try:
        joblib.dump(model, path)
        print(f"[저장 완료] 모델 → {path}")
    except Exception as e:
        raise RuntimeError(f"[ERROR] 모델 저장 실패 → {e}")