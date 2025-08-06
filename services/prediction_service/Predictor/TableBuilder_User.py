import os
import pandas as pd
from Predictor.PickleLoader import PickleLoader
from core_utiles.config_loader import BASE_OUTPUT_DIR

class TableBuilderUser:
    def __init__(self, config: dict):
        self.config = config
        self.models = PickleLoader(config=self.config).load()

        self.csv_path = os.path.join(BASE_OUTPUT_DIR, "유저데이터.csv")
        self.data_dir = self.config["PREDICTOR_CONFIG"]["IMPORT_CONFIG"]["CSV_CONFIG"]["FILE_PATH"]
        self.library_prefix = self.config["PREDICTOR_CONFIG"]["IMPORT_CONFIG"]["CSV_CONFIG"]["FILE_PREFIX"].split("_")[0]

        self.input_cols = config["INPUT_COLUMNS"]
        self.user_features = ["CPSS_CPS", "LPS_LPS", "VPS_VPS"]

    def _load_user_csv(self) -> pd.DataFrame:
        return pd.read_csv(self.csv_path)

    def _extract_user_year_data(self, row) -> list:
        records = []
        for nth in ["1ST", "2ND", "3RD", "4TH"]:
            try:
                yr = int(row[f"{nth}_YR"])
                cps = row[f"{nth}_USR_CPS"]
                lps = row[f"{nth}_USR_LPS"]
                vps = row[f"{nth}_USR_VPS"]
                records.append({
                    "YR": yr,
                    "CPSS_CPS": cps,
                    "LPS_LPS": lps,
                    "VPS_VPS": vps,
                    "label": f"SCR_EST_{nth}"
                })
            except:
                print(f"[SKIP] {row['USR_NAME']} 학년 데이터 누락")
        return records

    def _load_library_data(self, snm: str, yr: int) -> dict:
        filename = f"{self.library_prefix}_종합데이터_{yr}.csv"
        file_path = os.path.join(self.data_dir, filename)
        df = pd.read_csv(file_path)
        row_match = df[df["SNM"] == snm]
        if row_match.empty:
            raise ValueError(f"[ERROR] {snm} / {yr} 대학 데이터 없음")
        result = row_match.iloc[0].to_dict()
        return {col: result.get(col, 0) for col in self.input_cols if col not in ["YR"] + self.user_features}

    def predict(self) -> pd.DataFrame:
        df_user = self._load_user_csv()
        results = []

        for _, row in df_user.iterrows():
            usr_base = row.to_dict()
            snm = row["USR_SNM"]
            name = row["USR_NAME"]
            inputs = self._extract_user_year_data(row)

            user_result = usr_base.copy()
            for record in inputs:
                try:
                    lib_feats = self._load_library_data(snm, record["YR"])
                    merged = {
                        "YR": record["YR"],
                        "CPSS_CPS": record["CPSS_CPS"],
                        "LPS_LPS": record["LPS_LPS"],
                        "VPS_VPS": record["VPS_VPS"],
                        **lib_feats
                    }
                    df_input = pd.DataFrame([merged])
                    preds = self._predict_df(df_input)
                    user_result[record["label"]] = preds[0]
                except Exception as e:
                    print(f"[ERROR] {name} / {record['YR']} ➜ {e}")
                    user_result[record["label"]] = None

            results.append(user_result)
        return pd.DataFrame(results)

    def _predict_df(self, df: pd.DataFrame) -> list:
        X = df[self.input_cols].copy()

        if self.config["SCALER_CONFIG"].get("enabled", False):
            X = pd.DataFrame(self.models["scaler"].transform(X), columns=self.input_cols)

        if self.config["CLUSTER_CONFIG"].get("enabled", False):
            cluster_model = self.models["cluster_model"]
            cluster_id = cluster_model.predict(X)[0]
            model = self.models["rfr_clusters"][cluster_id]
        else:
            model = self.models["rfr_full"]

        return model.predict(X)

    def run(self):
        df = self.predict()
        out_dir = BASE_OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)

        out_path = os.path.join(out_dir, "유저환경점수.csv")
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"[저장 완료] {out_path}")

