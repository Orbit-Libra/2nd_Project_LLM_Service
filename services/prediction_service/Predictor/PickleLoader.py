import os
import joblib
from core_utiles.config_loader import MODEL_SAVE_PATH

class PickleLoader:
    def __init__(self, config: dict):
        self.config = config
        self.models = {}

        # __file__ 기준으로 경로 보정
        self.base_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), MODEL_SAVE_PATH)
        )

    def load(self):
        model_num = self.config["MODEL_NUM"]
        model_name = self.config["MODEL_NAME"]
        version = self.config["SAVE_NAME_RULES"]["version"]
        suffix = self.config["SAVE_NAME_RULES"]["suffix"]

        def build_filename(type_str: str) -> str:
            return f"{model_num}_{model_name}_{type_str}_{version}{suffix}"

        def safe_load(label: str, filename: str):
            path = os.path.join(self.base_dir, filename)
            print(f"[로딩] {label} -> {path}")
            if not os.path.exists(path):
                raise FileNotFoundError(f"파일 없음: {path}")
            return joblib.load(path)

        # 1. 스케일러 로딩
        if self.config.get("SCALER_CONFIG", {}).get("enabled", False):
            scaler_filename = build_filename("ScalerModel")
            self.models["scaler"] = safe_load("스케일러", scaler_filename)

        # 2. 클러스터링 모델 로딩
        cluster_cfg = self.config.get("CLUSTER_CONFIG", {})
        if cluster_cfg.get("enabled", False):
            cluster_filename = build_filename("ClusterModel")
            self.models["cluster_model"] = safe_load("클러스터링 모델", cluster_filename)

            n_clusters = cluster_cfg["params"]["KMeans"]["n_clusters"]
            self.models["rfr_clusters"] = []

            for i in range(n_clusters):
                filename = build_filename(f"cluster_{i}")
                self.models["rfr_clusters"].append(safe_load(f"클러스터 RFR({i})", filename))
        else:
            # 3. Full 모델 로딩
            filename = build_filename("Full")
            self.models["rfr_full"] = safe_load("Full RFR", filename)

        return self.models
