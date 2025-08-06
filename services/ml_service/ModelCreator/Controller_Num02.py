import os
import json
import oracledb
import pandas as pd
import numpy as np
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core_utiles.config_loader import (
    MODEL_SAVE_PATH, LOG_SAVE_PATH,
    ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN, ORACLE_CLIENT_PATH,
    get_raw_years
)

from ModelCreator.Fetcher import DataFetcher
from ModelCreator.Cleaner import DataCleaner
from ModelCreator.Trainer import ModelTrainer
from ModelCreator.Utiles.Exporter import save_model
from ModelCreator.Logger import PipelineLogger

class PipelineController:
    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.conn = None

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
        print("[START] Num02 (XGB 통합모델) 학습 컨트롤러 시작")

        window_cfg = self.config.get("WINDOW_CONFIG", {})
        window_size = window_cfg.get("window_size", 5)
        test_size = self.config.get("TEST_SIZE", 0.2)
        model_type = self.config["MODEL_TYPE"]
        model_num = self.config["MODEL_NUM"]
        model_name = self.config["MODEL_NAME"]
        save_rules = self.config["SAVE_NAME_RULES"]

        raw_years = get_raw_years()
        if len(raw_years) < window_size + 1:
            print(f"[ERROR] 연도 범위 부족 ➜ RAW_DATA_RANGE={raw_years}")
            return

        min_year = raw_years[0]
        max_year = raw_years[-1]

        # DB 연결
        if self.config["TABLE_TYPE"] == "DB":
            self.setup_db_connection()

        # 데이터 수집 및 전처리
        fetcher = DataFetcher(config=self.config, conn=self.conn)
        df_raw = fetcher.fetch()

        cleaner = DataCleaner(config=self.config)
        df_cleaned = cleaner.clean_numeric(df_raw, df_raw.columns.tolist())
        df_cleaned = cleaner.handle_missing(df_cleaned, df_raw.columns.tolist())
        df_cleaned = cleaner.handle_outliers(df_cleaned, df_raw.columns.tolist())

        # 전체 학습셋 구성
        X_total, y_total = [], []

        for start_year in range(min_year, max_year - window_size + 1):
            input_cols = [f"SCR_EST_{y}" for y in range(start_year, start_year + window_size)]
            target_col = f"SCR_EST_{start_year + window_size}"

            expected_cols = input_cols + [target_col]
            if not all(col in df_cleaned.columns for col in expected_cols):
                print(f"[SKIP] 누락된 컬럼: {expected_cols}")
                continue

            df_sub = df_cleaned[expected_cols].dropna()
            print(f"[DEBUG] 입력: {input_cols} -> 타겟: {target_col} -> 샘플 수: {len(df_sub)}")
            if df_sub.empty:
                continue

            X_total.append(df_sub[input_cols].values)
            y_total.append(df_sub[target_col].values)

        if not X_total or not y_total:
            print("[ERROR] 유효한 학습셋이 생성되지 않았습니다.")
            return

        # 통합 학습셋 구성
        X_all = np.vstack(X_total)
        y_all = np.concatenate(y_total)
        df_all = pd.DataFrame(np.column_stack([X_all, y_all]), columns=[f"F{i}" for i in range(X_all.shape[1])] + ["Target"])

        # 모델 학습
        trainer = ModelTrainer(
            model_type=model_type,
            params_by_cluster=self.config["PARAMS"],
            input_cols=[col for col in df_all.columns if col != "Target"],
            test_size=test_size,
            target_col="Target",
            cluster_enabled=False
        )
        metrics = trainer.train_full_model(df_all, target_col="Target")[0]

        # 저장
        os.makedirs(MODEL_SAVE_PATH, exist_ok=True)
        os.makedirs(LOG_SAVE_PATH, exist_ok=True)

        version = save_rules["version"]
        suffix = save_rules["suffix"]
        filename = f"{model_num}_{model_name}_full_{version}{suffix}"
        save_path = os.path.join(MODEL_SAVE_PATH, filename)
        save_model(trainer.models_by_cluster["full"], save_path)

        log_filename = f"{model_num}_{model_name}_{version}_Log.json"
        logger = PipelineLogger(LOG_SAVE_PATH)
        logger.save_log(filename=log_filename, full_metrics=metrics, config=self.config)

        print(f"\n[COMPLETE] 단일 통합 모델 학습 및 저장 완료 -> {filename}")
