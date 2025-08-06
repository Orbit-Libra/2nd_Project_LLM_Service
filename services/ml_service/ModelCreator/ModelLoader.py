from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

class ModelFactory:
    @staticmethod
    def get_model(model_type: str, cluster_id: str, params_dict: dict):
        cluster_id = str(cluster_id)
        params = params_dict.get(cluster_id)

        if params is None:
            raise ValueError(f"[ERROR] 클러스터 '{cluster_id}'에 대한 파라미터가 없습니다.")

        if model_type == "RandomForestRegressor":
            return RandomForestRegressor(**params)
        elif model_type == "XGBRegressor":
            return XGBRegressor(**params)
        else:
            raise ValueError(f"[ERROR] 지원하지 않는 모델 타입: {model_type}")