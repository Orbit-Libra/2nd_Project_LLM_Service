import pandas as pd

class EnNameCollector:
    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path

    def run(self):
        # CSV 불러오기
        try:
            df = pd.read_csv(self.input_path)
        except Exception as e:
            print(f"CSV 로딩 실패: {e}")
            return

        if "Institution" not in df.columns:
            print("'Institution' 컬럼이 없습니다.")
            return

        # 대학명 추출 & 중복 제거
        institutions = sorted(set(df["Institution"].dropna().str.strip()))

        # 저장
        output_df = pd.DataFrame({"Institution": institutions})
        output_df.to_csv(self.output_path, index=False, encoding="utf-8-sig")
        print(f"대학명 리스트 저장 완료: {self.output_path}")