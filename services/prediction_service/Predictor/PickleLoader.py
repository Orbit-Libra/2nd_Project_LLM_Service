import os
import joblib
from core_utiles.config_loader import MODEL_SAVE_PATH

class PickleLoader:
    def __init__(self, config: dict):
        self.config = config
        self.models = {}

    def load(self):
        model_num = self.config["MODEL_NUM"]
        model_name = self.config["MODEL_NAME"]
        version = self.config["SAVE_NAME_RULES"]["version"]
        suffix = self.config["SAVE_NAME_RULES"]["suffix"]

        base_dir = MODEL_SAVE_PATH  # .env에서 불러온 경로

        def build_filename(type_str: str) -> str:
            return f"{model_num}_{model_name}_{type_str}_{version}{suffix}"

        # 1. 스케일러 로딩
        if self.config.get("SCALER_CONFIG", {}).get("enabled", False):
            scaler_filename = build_filename("ScalerModel")
            scaler_path = os.path.join(base_dir, scaler_filename)
            print(f"[로딩] 스케일러 -> {scaler_path}")
            self.models["scaler"] = joblib.load(scaler_path)

        # 2. 클러스터링 모델 로딩
        cluster_cfg = self.config.get("CLUSTER_CONFIG", {})
        if cluster_cfg.get("enabled", False):
            cluster_filename = build_filename("ClusterModel")
            cluster_path = os.path.join(base_dir, cluster_filename)
            print(f"[로딩] 클러스터링 모델 -> {cluster_path}")
            self.models["cluster_model"] = joblib.load(cluster_path)

            n_clusters = cluster_cfg["params"]["KMeans"]["n_clusters"]
            self.models["rfr_clusters"] = []

            for i in range(n_clusters):
                filename = build_filename(f"cluster_{i}")
                model_path = os.path.join(base_dir, filename)
                print(f"[로딩] 클러스터 RFR({i}) -> {model_path}")
                self.models["rfr_clusters"].append(joblib.load(model_path))
        else:
            # 3. Full 모델 로딩
            filename = build_filename("Full")
            model_path = os.path.join(base_dir, filename)
            print(f"[로딩] Full RFR -> {model_path}")
            self.models["rfr_full"] = joblib.load(model_path)

        return self.models