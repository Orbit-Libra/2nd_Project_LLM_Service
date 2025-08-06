import os
import pandas as pd
from core_utiles.config_loader import get_raw_years
from core_utiles.OracleTableCreater import OTC
from Predictor.PickleLoader import PickleLoader

class TableBuilder:
    def __init__(self, config: dict, conn, engine):
        self.config = config
        self.conn = conn
        self.engine = engine
        self.models = PickleLoader(config=self.config).load()

        self.import_cfg = self.config["PREDICTOR_CONFIG"]["IMPORT_CONFIG"]
        self.export_cfg = self.config["PREDICTOR_CONFIG"]["EXPORT_CONFIG"]
        self.missing_cfg = self.config["PREDICTOR_CONFIG"].get("MISSING_VALUE_STRATEGY", {})
        self.window_size = self.config.get("WINDOW_CONFIG", {}).get("window_size", 3)

    def _load_data(self) -> pd.DataFrame:
        table_type = self.import_cfg["TABLE_TYPE"]

        if table_type == "DB":
            table_name = self.import_cfg["DB_CONFIG"]["TABLE_PREFIX"]
            query = f"SELECT * FROM LIBRA.{table_name}"
            return pd.read_sql(query, con=self.conn)

        elif table_type == "CSV":
            filename = f"{self.import_cfg['CSV_CONFIG']['FILE_PREFIX']}.csv"
            path = self.import_cfg["CSV_CONFIG"]["FILE_PATH"]
            return pd.read_csv(os.path.join(path, filename))

        else:
            raise ValueError(f"[ERROR] 지원되지 않는 TABLE_TYPE: {table_type}")

    def _predict_for_year(self, df: pd.DataFrame, year: int) -> pd.Series:
        input_cols = [f"SCR_EST_{y}" for y in range(year - self.window_size, year)]

        # 입력 피처셋 유효성 확인
        missing_cols = [col for col in input_cols if col not in df.columns]
        if missing_cols:
            raise KeyError(f"[ERROR] 예측 대상 연도 {year}의 입력 피처 누락 ➜ {missing_cols}")

        df_input = df[input_cols].copy()
        original_names = df_input.columns.tolist()
        df_input.columns = [f"F{i}" for i in range(df_input.shape[1])]  # XGB 호환

        # 스케일링 적용
        if self.config["SCALER_CONFIG"].get("enabled", False) and "scaler" in self.models:
            scaler = self.models["scaler"]
            df_input.iloc[:, :] = scaler.transform(df_input)

        model = self.models["rfr_full"]
        preds = model.predict(df_input)

        # 이상치 비율 기반 널 처리
        if self.missing_cfg.get("nullify_score_by_row", False):
            zero_ratio = df[input_cols].apply(lambda row: (row == 0).mean(), axis=1)
            preds = [None if ratio > self.missing_cfg.get("zero_threshold_ratio", 0.5) else p
                    for p, ratio in zip(preds, zero_ratio)]

        return pd.Series(preds, name=f"SCR_EST_{year}")

    def _export_final(self, df: pd.DataFrame):
        db_prefix = self.export_cfg["DB_CONFIG"]["TABLE_PREFIX"]
        csv_prefix = self.export_cfg["CSV_CONFIG"]["FILE_PREFIX"]
        csv_path = self.export_cfg["CSV_CONFIG"]["FILE_PATH"]

        table_name = f"{db_prefix}"
        file_name = f"{csv_prefix}.csv"
        file_path = os.path.join(csv_path, file_name)

        df_out = df.sort_values(by="ID").reset_index(drop=True)
        OTC(cursor=self.conn.cursor(), table_name=table_name, df=df_out)
        df_out.to_sql(name=table_name, con=self.engine, if_exists="append", index=False)
        df_out.to_csv(file_path, index=False, encoding="utf-8-sig")
        print(f"[저장 완료] {table_name} / {file_name}")

    def run(self):
        raw_years = get_raw_years()
        future_years = [raw_years[-1] + i for i in range(1, 3)]

        df = self._load_data()
        remain_cols = self.export_cfg.get("REMAIN_COLS", [])

        # 최종 결과에 포함될 모든 점수 컬럼 구성 (과거 + 예측 대상)
        score_cols = [f"SCR_EST_{y}" for y in raw_years + future_years]

        # 존재하는 컬럼만 사용
        available_score_cols = [col for col in score_cols if col in df.columns]
        df_accum = df[remain_cols + available_score_cols].copy()

        # 예측 대상 연도별 점수 생성
        for year in future_years:
            print(f"[예측 진행] SCR_EST_{year}")
            pred_col = self._predict_for_year(df_accum, year)
            df_accum[f"SCR_EST_{year}"] = pred_col

        # 최종 결과 내보내기
        df_final = df_accum.drop(columns=["YR"], errors="ignore")
        self._export_final(df_final)

