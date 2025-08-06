import os
import sys
import json
import oracledb

# 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core_utiles.config_loader import (
    MODEL_SAVE_PATH, LOG_SAVE_PATH,
    ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN, ORACLE_CLIENT_PATH
)

from ModelCreator.Fetcher import DataFetcher
from ModelCreator.Cleaner import DataCleaner
from ModelCreator.Handler import DataHandler
from ModelCreator.Trainer import ModelTrainer
from ModelCreator.Utiles.Exporter import save_model
from ModelCreator.Utiles.Evaluator import evaluate_metrics
from ModelCreator.Logger import PipelineLogger

class PipelineController:
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.conn = None

    def load_config(self, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def setup_db_connection(self):
        if ORACLE_CLIENT_PATH:
            oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_PATH)
            self.conn = oracledb.connect(
                user=ORACLE_USER,
                password=ORACLE_PASSWORD,
                dsn=ORACLE_DSN
            )
            print("[INFO] Oracle DB 연결 완료")

    def run(self):
        print("[START] 모델 생성 파이프라인 시작")

        # 설정값
        model_type = self.config["MODEL_TYPE"]
        model_name = self.config["MODEL_NAME"]
        input_cols = self.config["INPUT_COLUMNS"]
        target_col = self.config["TARGET_COLUMN"]
        save_rules = self.config["SAVE_NAME_RULES"]
        model_num = self.config["MODEL_NUM"]
        cluster_enabled = self.config["CLUSTER_CONFIG"].get("enabled", False)
        test_size = self.config.get("TEST_SIZE", 0.2)

        # 저장 경로
        model_dir = MODEL_SAVE_PATH
        log_dir = LOG_SAVE_PATH
        os.makedirs(model_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)

        # DB 연결
        if self.config["TABLE_TYPE"] == "DB":
            self.setup_db_connection()

        # 1. 데이터 수집
        fetcher = DataFetcher(config=self.config, conn=self.conn)
        df_raw = fetcher.fetch()

        # 2. 전처리
        cleaner = DataCleaner(config=self.config)
        df_cleaned = cleaner.clean_numeric(df_raw, input_cols + [target_col])
        df_cleaned = cleaner.handle_missing(df_cleaned, input_cols + [target_col])
        df_cleaned = cleaner.handle_outliers(df_cleaned, input_cols)

        # 3. 스케일링 & 클러스터링
        handler = DataHandler(
            scaler_config=self.config["SCALER_CONFIG"],
            cluster_config=self.config["CLUSTER_CONFIG"]
        )
        df_scaled = handler.scale_features(df_cleaned, input_cols)
        df_clustered = handler.assign_clusters(df_scaled, input_cols)

        # 4. 모델 학습
        trainer = ModelTrainer(
            model_type=model_type,
            params_by_cluster=self.config["PARAMS"],
            input_cols=input_cols,
            cluster_enabled=cluster_enabled,
            target_col=target_col,
            test_size=test_size
        )
        full_metrics, X_test, y_test = trainer.train_full_model(df_clustered, target_col)
        cluster_metrics = trainer.train_by_cluster(df_clustered)

        print("[INFO] 모델 학습 완료 → 평가 지표:")
        print("-> Full 모델")
        for key, value in full_metrics.items():
            print(f"  - {key}: {value:.4f}")

        if cluster_metrics:
            print("-> 클러스터별 모델")
            for cluster_id, metric in cluster_metrics.items():
                print(f"  -> 클러스터 '{cluster_id}'")
                for key, value in metric.items():
                    print(f"    - {key}: {value:.4f}")

        # 5. 모델 저장
        for cid, model in trainer.models_by_cluster.items():
            if cid == "full":
                filename = f"{model_num}_{model_name}_full_{save_rules['version']}{save_rules['suffix']}"
            else:
                filename = f"{model_num}_{model_name}_cluster_{cid}_{save_rules['version']}{save_rules['suffix']}"
            path = os.path.join(model_dir, filename)
            save_model(model, path)

        # 5-1. 스케일러 저장
        if handler.scaler:
            scaler_path = os.path.join(model_dir, f"{model_num}_{model_name}_{save_rules['prefix_model_scaler']}_{save_rules['version']}.pkl")
            save_model(handler.scaler, scaler_path)

        # 5-2. 클러스터 모델 저장
        if cluster_enabled and handler.cluster_model:
            cluster_path = os.path.join(model_dir, f"{model_num}_{model_name}_{save_rules['prefix_model_cluster']}_{save_rules['version']}.pkl")
            save_model(handler.cluster_model, cluster_path)

        # 6. 클러스터링 기반 예측 성능 평가
        clustered_metrics = None
        if cluster_enabled and handler.cluster_model:
            if handler.scaler:
                X_test_scaled = handler.scaler.transform(X_test)
            else:
                X_test_scaled = X_test
            cluster_ids = handler.cluster_model.predict(X_test_scaled)

            y_pred_all = []
            for i, cluster_id in enumerate(cluster_ids):
                model = trainer.models_by_cluster.get(cluster_id)
                if model is None:
                    raise ValueError(f"[ERROR] 클러스터 '{cluster_id}'에 해당하는 모델이 없습니다.")
                x_sample = X_test.iloc[i:i+1]
                y_pred_all.append(model.predict(x_sample)[0])

            clustered_metrics = evaluate_metrics(y_test, y_pred_all)

        # 7. 로그 저장 (Logger 클래스 사용)
        logger = PipelineLogger(log_dir)
        log_filename = f"{model_num}_{model_name}_{save_rules['version']}_Log.json"
        log_data = logger.save_log(
            filename=log_filename,
            full_metrics=full_metrics,
            clustered_metrics=clustered_metrics,
            cluster_enabled=cluster_enabled,
            config=self.config,
            cluster_metrics=cluster_metrics
        )

        # 8. 최종 성능 출력
        print("\n[최종 성능 지표]")
        print("-> FULL 모델")
        for key, value in log_data["full"].items():
            print(f"  - {key}: {value:.4f}")

        if cluster_enabled and "clustered" in log_data:
            print("-> CLUSTERED 모델")
            for key, value in log_data["clustered"].items():
                print(f"  - {key}: {value:.4f}")

        return log_data