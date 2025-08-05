import os
import pandas as pd
from core_utiles.OracleTableCreater import OTC  # 테이블 생성 모듈

class CSVToOracleUploader:
    def __init__(self, db, csv_dir):
        self.db = db
        self.csv_dir = csv_dir
        self.file_list = [f for f in os.listdir(csv_dir) if f.endswith(".csv")]

    def run(self):
        cursor = self.db.cursor
        conn = self.db.conn

        for filename in self.file_list:
            path = os.path.join(self.csv_dir, filename)
            df = pd.read_csv(path, encoding="utf-8")

            for col in df.columns:
                if len(col.encode("utf-8")) > 30:
                    print(f"[파일: {filename}] 컬럼명 '{col}' → 30 byte 초과")

            name_parts = filename.replace('.csv', '').split('_')
            try:
                table_name = f"{name_parts[0]}_{name_parts[2]}".upper()
            except IndexError:
                print(f"[파일: {filename}] 테이블명 추출 실패 - 파일명 형식 확인 필요")
                continue

            try:
                OTC(cursor, table_name, df)
                print(f"테이블 {table_name} 생성 완료")
            except Exception as e:
                print(f"테이블 생성 오류 ({table_name}): {e}")
                continue

            columns = df.columns.tolist()
            placeholders = ', '.join([f':{i+1}' for i in range(len(columns))])
            col_names = ', '.join([f'"{col}"' for col in columns])
            insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'
            data = [tuple(row) for row in df.values]

            try:
                cursor.executemany(insert_sql, data)
                conn.commit()
                print(f"{filename} → {table_name} 삽입 완료 ({len(data)}건)")
            except Exception as e:
                print(f"삽입 오류 ({filename}): {e}")