import os
import pandas as pd
from Predictor.PickleLoader import PickleLoader
from core_utiles.config_loader import OUTPUT_DIR
import pandas as pd

class TableBuilderUser:
    def __init__(self, config: dict, conn=None, engine=None, models=None):
        self.config = config
        self.conn = conn
        self.engine = engine
        self.models = models or PickleLoader(config=self.config).load()

        self.csv_path = os.path.join(OUTPUT_DIR, "유저데이터.csv")
        icfg = self.config["PREDICTOR_CONFIG"]["IMPORT_CONFIG"]
        self.import_cfg = icfg
        self.data_dir = icfg["CSV_CONFIG"]["FILE_PATH"]
        self.library_prefix = icfg["CSV_CONFIG"]["FILE_PREFIX"].split("_")[0]

        self.input_cols = config["INPUT_COLUMNS"]
        self.user_features = ["CPSS_CPS", "LPS_LPS", "VPS_VPS"]

    # === 기존 배치용 ===
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
                pass
        return records

    def _load_library_data_csv(self, snm: str, yr: int) -> dict:
        filename = f"{self.library_prefix}_종합데이터_{yr}.csv"
        base_dir = os.path.dirname(__file__)
        rel_path = os.path.normpath(os.path.join(base_dir, "..", "..", "..", self.data_dir))
        df = pd.read_csv(os.path.join(rel_path, filename))
        row_match = df[df["SNM"] == snm]
        if row_match.empty:
            raise ValueError(f"[ERROR] {snm} / {yr} 대학 데이터 없음(CSV)")
        result = row_match.iloc[0].to_dict()
        return {col: result.get(col, 0) for col in self.input_cols if col not in ["YR"] + self.user_features}

    def _load_library_data_db(self, snm: str, yr: int) -> dict:
        if self.conn is None:
            raise RuntimeError("DB 연결이 없습니다. conn=None")
        prefix = self.import_cfg["DB_CONFIG"]["TABLE_PREFIX"]  # 예: ESTIMATIONFUTURE_YYYY or VIEW명 등
        # 연도별 테이블 명 만들 필요가 있으면 여기서 조정
        table_name = f"{prefix}_{yr}" if "{yr}" not in prefix else prefix.format(yr=yr)
        query = f"SELECT * FROM {table_name} WHERE SNM = :1"
        df = pd.read_sql(query, con=self.conn, params=[snm])
        if df.empty:
            raise ValueError(f"[ERROR] {snm} / {yr} 대학 데이터 없음(DB)")
        row = df.iloc[0].to_dict()
        return {col: row.get(col, 0) for col in self.input_cols if col not in ["YR"] + self.user_features}

    def _load_library_data(self, snm: str, yr: int) -> dict:
        ttype = self.import_cfg["TABLE_TYPE"]
        if ttype == "CSV":
            return self._load_library_data_csv(snm, yr)
        elif ttype == "DB":
            return self._load_library_data_db(snm, yr)
        else:
            raise ValueError(f"[ERROR] 지원되지 않는 TABLE_TYPE: {ttype}")

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

    # === 배치 실행 ===
    def run(self):
        df = self.predict()
        out_dir = OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "유저환경점수.csv")
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"[저장 완료] {out_path}")

    # === 기존 배치 예측 ===
    def predict(self) -> pd.DataFrame:
        df_user = self._load_user_csv()
        results = []

        for _, row in df_user.iterrows():
            usr_base = row.to_dict()
            snm = row["USR_SNM"]
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
                    user_result[record["label"]] = float(preds[0])
                except Exception as e:
                    print(f"[ERROR] {snm} / {record['YR']} ➜ {e}")
                    user_result[record["label"]] = None

            results.append(user_result)
        return pd.DataFrame(results)

    # === ✅ API용: payload(JSON) 기반 예측 ===
    def predict_from_payload(self, payload: dict) -> dict:
        """
        payload 예시:
        {
          "USR_SNM": "서울대학교",
          "1ST_YR": 2022, "1ST_USR_CPS":1234.5, "1ST_USR_LPS":10, "1ST_USR_VPS":20,
          "2ND_YR": ..., ...
          ...
        }
        """
        required_base = ["USR_SNM"]
        for k in required_base:
            if k not in payload or str(payload[k]).strip() == "":
                raise ValueError(f"필수 항목 누락: {k}")

        snm = payload["USR_SNM"]
        results = {}

        for nth in ["1ST", "2ND", "3RD", "4TH"]:
            yr_key = f"{nth}_YR"
            cps_key = f"{nth}_USR_CPS"
            lps_key = f"{nth}_USR_LPS"
            vps_key = f"{nth}_USR_VPS"

            if yr_key not in payload:
                continue  # 해당 학년 미입력시 스킵

            try:
                yr = int(payload[yr_key])
                cps = float(payload.get(cps_key, 0) or 0)
                lps = float(payload.get(lps_key, 0) or 0)
                vps = float(payload.get(vps_key, 0) or 0)

                lib_feats = self._load_library_data(snm, yr)
                merged = {
                    "YR": yr,
                    "CPSS_CPS": cps,
                    "LPS_LPS": lps,
                    "VPS_VPS": vps,
                    **lib_feats
                }
                df_input = pd.DataFrame([merged])
                pred = float(self._predict_df(df_input)[0])
                results[f"SCR_EST_{nth}"] = pred
            except Exception as e:
                results[f"SCR_EST_{nth}"] = None

        return results
