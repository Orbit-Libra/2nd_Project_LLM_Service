import pandas as pd

class DataCleaner:
    def __init__(self, config: dict):
        self.missing_strategy = config.get("MISSING_VALUE_STRATEGY", {})
        self.outlier_strategy = config.get("OUTLIER_STRATEGY", {})

    def clean_numeric(self, df: pd.DataFrame, numeric_cols: list) -> pd.DataFrame:
        df.columns = df.columns.str.strip()
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
        return df

    def handle_missing(self, df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
        if not self.missing_strategy.get("enable", False):
            print("[INFO] 결측치 처리 비활성화됨")
            return df

        method = self.missing_strategy.get("method", "drop")
        fill_value = self.missing_strategy.get("fill_value", 0)
        zero_threshold = self.missing_strategy.get("zero_threshold_ratio", 0.5)
        remove_col = self.missing_strategy.get("remove_zero_by_column", False)
        remove_row = self.missing_strategy.get("remove_zero_by_row", False)

        # 컬럼 기준 제거
        if remove_col:
            for col in feature_cols:
                zero_ratio = (df[col] == 0).mean()
                if zero_ratio > zero_threshold:
                    print(f"[INFO] '{col}' 컬럼 제거 (0값 비율: {zero_ratio:.2f})")
                    df = df.drop(columns=[col])
                    feature_cols.remove(col)
            

        # 행 기준 제거
        if remove_row:
            def row_zero_ratio(row):
                return (row[feature_cols] == 0).mean()

            df["__zero_ratio__"] = df.apply(row_zero_ratio, axis=1)
            to_remove = df[df["__zero_ratio__"] > zero_threshold]

            if not to_remove.empty:
                for idx, row in to_remove.iterrows():
                    row_snm = row.get("SNM", f"index_{idx}")
                    print(f"[INFO] '{row_snm}' 데이터행 제거 (0값 비율: {row['__zero_ratio__']:.2f})")

            df = df[df["__zero_ratio__"] <= zero_threshold].drop(columns=["__zero_ratio__"])

        # 결측치 처리
        if method == "drop":
            df = df.dropna()
        elif method == "fill":
            df = df.fillna(fill_value)
        else:
            raise ValueError(f"[ERROR] 지원하지 않는 결측치 처리 방식: {method}")

        return df

    def handle_outliers(self, df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
        if not self.outlier_strategy.get("enable", False):
            print("[INFO] 이상치 처리 비활성화됨")
            return df

        method = self.outlier_strategy.get("method", "iqr")
        threshold = self.outlier_strategy.get("threshold", 1.5)

        if method == "iqr":
            for col in feature_cols:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - threshold * IQR
                upper = Q3 + threshold * IQR
                before = len(df)
                df = df[(df[col] >= lower) & (df[col] <= upper)]
                after = len(df)
                print(f"[INFO] '{col}' 이상치 제거 → {before - after}개 제거됨")
        else:
            raise ValueError(f"[ERROR] 지원하지 않는 이상치 처리 방식: {method}")

        return df