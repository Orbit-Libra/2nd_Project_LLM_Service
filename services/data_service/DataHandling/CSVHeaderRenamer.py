import os
import pandas as pd
import csv

class CSVHeaderRenamer:
    def __init__(self, csv_folder: str, mapping_path: str, encoding: str = "utf-8-sig"):
        self.csv_folder = csv_folder
        self.mapping = self.load_mapping(mapping_path)
        self.encoding = encoding

    def load_mapping(self, path: str) -> dict:
        mapping = {}
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if "한글헤더" not in reader.fieldnames or "영문약어" not in reader.fieldnames:
                raise ValueError("매핑 CSV 파일에 '한글헤더', '영문약어' 컬럼이 필요합니다.")
            for row in reader:
                korean = row["한글헤더"].strip()
                english = row["영문약어"].strip()
                if korean and english:
                    mapping[korean] = english
        return mapping

    def rename_tokens(self, col_name: str) -> str:
        tokens = col_name.split("_")
        new_tokens = [self.mapping.get(token.strip(), token.strip()) for token in tokens]
        return "_".join(new_tokens)

    # 열 번호 -> 엑셀 열 변한
    def column_index_to_excel_letter(self, n: int) -> str:
        result = ""
        while n >= 0:
            result = chr(n % 26 + 65) + result
            n = n // 26 - 1
        return result

    def process_all_csvs(self):
        for filename in os.listdir(self.csv_folder):
            if filename.lower().endswith(".csv"):
                path = os.path.join(self.csv_folder, filename)
                try:
                    df = pd.read_csv(path, encoding=self.encoding)
                    original_columns = df.columns.tolist()
                    renamed_columns = [self.rename_tokens(col) for col in original_columns]
                    df.columns = renamed_columns

                    # 덮어쓰기 저장
                    df.to_csv(path, index=False, encoding=self.encoding)

                    # 최대 byte 수 컬럼 찾기
                    max_col = max(renamed_columns, key=lambda col: len(col.encode("utf-8")))
                    max_byte = len(max_col.encode("utf-8"))
                    col_index = renamed_columns.index(max_col)
                    excel_col_letter = self.column_index_to_excel_letter(col_index)

                    print(f"변환 및 저장 완료: {filename}")
                    print(f"가장 긴 컬럼명: {max_col} → {max_byte} bytes → {excel_col_letter}열")
                    for col in renamed_columns:
                        byte_len = len(col.encode("utf-8"))
                        if byte_len > 30:
                            col_index = renamed_columns.index(col)
                            excel_col = self.column_index_to_excel_letter(col_index)
                            print(f"byte초과 : {col} → {byte_len} bytes → {excel_col}열")


                except Exception as e:
                    print(f"오류 발생: {filename} → {e}")