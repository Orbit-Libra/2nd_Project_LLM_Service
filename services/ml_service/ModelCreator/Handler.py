import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering

class DataHandler:
    def __init__(self, scaler_config: dict, cluster_config: dict):
        self.scaler_config = scaler_config
        self.cluster_config = cluster_config
        self.scaler = None
        self.cluster_model = None

    def scale_features(self, df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
        if not self.scaler_config.get("enabled", False):
            print("[INFO] 스케일링 비활성화됨")
            return df

        scaler_type = self.scaler_config.get("type", "StandardScaler")
        scaler_params = self.scaler_config.get("params", {})

        if scaler_type == "StandardScaler":
            self.scaler = StandardScaler(**scaler_params)
        elif scaler_type == "MinMaxScaler":
            self.scaler = MinMaxScaler(**scaler_params)
        elif scaler_type == "RobustScaler":
            self.scaler = RobustScaler(**scaler_params)
        else:
            raise ValueError(f"[ERROR] 지원하지 않는 스케일러 타입: {scaler_type}")

        scaled_array = self.scaler.fit_transform(df[feature_cols])
        df_scaled = df.copy()
        df_scaled[feature_cols] = scaled_array  # 기존 df에 덮어쓰기
        print(f"[INFO] '{scaler_type}' 스케일링 적용 완료")
        return df_scaled

    def assign_clusters(self, df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
        if not self.cluster_config.get("enabled", False):
            print("[INFO] 클러스터링 비활성화됨")
            df["cluster_id"] = "full"
            return df
        cluster_type = self.cluster_config.get("type", "KMeans")
        all_params = self.cluster_config.get("params", {})
        cluster_params = all_params.get(cluster_type, {})

        if cluster_type == "KMeans":
            self.cluster_model = KMeans(**cluster_params)
        elif cluster_type == "DBSCAN":
            self.cluster_model = DBSCAN(**cluster_params)
        elif cluster_type == "AgglomerativeClustering":
            self.cluster_model = AgglomerativeClustering(**cluster_params)
        else:
            raise ValueError(f"[ERROR] 지원하지 않는 클러스터링 타입: {cluster_type}")

        cluster_ids = self.cluster_model.fit_predict(df[feature_cols])
        df["cluster_id"] = cluster_ids
        print(f"[INFO] '{cluster_type}' 클러스터링 적용 완료 → 클러스터 수: {len(set(cluster_ids))}")
        return df