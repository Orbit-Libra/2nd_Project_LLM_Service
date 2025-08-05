import os
import csv
from core_utiles.Mapper import HMP  # 헤더 매핑 함수

class HeaderAbbreviationMapper:
    def __init__(self, input_path: str, output_path: str):
        self.input_path = input_path     # 한글 헤더 텍스트 또는 CSV 경로
        self.output_path = output_path   # 매핑 테이블 저장 경로
        self.original_headers = set()
        self.mapping = {}

    def load_headers(self):
        ext = os.path.splitext(self.input_path)[-1].lower()
        if ext == ".txt":
            with open(self.input_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.original_headers.add(line)
        elif ext == ".csv":
            with open(self.input_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if "한글헤더" not in reader.fieldnames:
                    raise ValueError("CSV 파일에 '한글헤더' 컬럼이 존재하지 않습니다.")
                for row in reader:
                    value = row["한글헤더"].strip()
                    if value:
                        self.original_headers.add(value)
        else:
            raise ValueError("지원되지 않는 입력 파일 형식입니다 (.txt 또는 .csv만 가능)")

    def generate_abbreviations(self):
        for h in sorted(self.original_headers):
            abbr = HMP(h)  # 외부 매핑 함수 사용
            self.mapping[h] = abbr

    def save_mapping_csv(self):
        with open(self.output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["한글헤더", "영문약어"])
            for original in sorted(self.original_headers):
                english = HMP(original)
                writer.writerow([original, english])
                if original == english:
                    print(f"매핑 없음: {original}")
        print(f"저장경로 : {self.output_path}")
        print(f"영문 약어 매핑 CSV 저장 완료")

    def check_duplicate_abbreviations_from_file(self):
        duplicates = {}
        seen = {}

        try:
            with open(self.output_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    korean = row["한글헤더"].strip()
                    english = row["영문약어"].strip()
                    if english in seen:
                        duplicates.setdefault(english, set()).update([korean, seen[english]])
                    else:
                        seen[english] = korean

            if duplicates:
                print("\n중복된 영문약어 발견:")
                for abbr, headers in duplicates.items():
                    print(f"  - {abbr} <- {sorted(headers)}")
            else:
                print("모든 영문약어가 유일합니다.")
            print("영문약어 무결성 검사 완료.")
        except Exception as e:
            print(f"무결성 검사 중 오류 발생: {e}")

    def run(self):
        self.load_headers()
        self.generate_abbreviations()
        self.save_mapping_csv()
        self.check_duplicate_abbreviations_from_file()