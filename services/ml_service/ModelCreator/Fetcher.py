import pandas as pd
import os

class DataFetcher:
    def __init__(self, config: dict, conn=None):
        self.config = config
        self.table_type = config.get("TABLE_TYPE", "DB")
        self.sort_config = config.get("SORT_COLUMNS", {})
        self.db_table_name = config.get("DB_TABLE_NAME")
        self.csv_dir = config.get("CSV_DIR")
        self.csv_file_name = config.get("SCV_DATA_NAME") + ".csv"
        self.conn = conn  # DB 연결 객체는 외부에서 주입

    def fetch(self) -> pd.DataFrame:
        if self.table_type == "DB":
            if self.conn is None:
                raise ValueError("[ERROR] DB 연결 객체가 없습니다.")

            order_clause = ""
            if self.sort_config:
                order_clause = " ORDER BY " + ", ".join(
                    f"{col} {direction.upper()}" for col, direction in self.sort_config.items()
                )

            query = f"SELECT * FROM {self.db_table_name}{order_clause}"
            df = pd.read_sql(query, con=self.conn)
            return df

        elif self.table_type == "CSV":
            csv_path = os.path.join(self.csv_dir, self.csv_file_name)
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"[ERROR] CSV 파일을 찾을 수 없습니다 → {csv_path}")

            df = pd.read_csv(csv_path)

            if self.sort_config:
                sort_cols = list(self.sort_config.keys())
                ascending_flags = [self.sort_config[col].upper() != "DESC" for col in sort_cols]
                df = df.sort_values(by=sort_cols, ascending=ascending_flags).reset_index(drop=True)

            return df

        else:
            raise ValueError(f"[ERROR] 지원하지 않는 TABLE_TYPE: {self.table_type}")