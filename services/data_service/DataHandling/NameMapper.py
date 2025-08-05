import pandas as pd
from core_utiles.Mapper import NMP  # 외부 매핑 함수 호출

class NameMapper:
    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path

    def run(self):
        try:
            df = pd.read_csv(self.input_path)
        except Exception as e:
            print(f"입력 파일 로딩 실패: {e}")
            return

        if "Institution" not in df.columns:
            print("'Institution' 컬럼이 없습니다.")
            return

        # 매핑 수행
        df["Korean_Name"] = df["Institution"].apply(NMP)  # 외부 함수 활용

        # 매핑 누락 항목 확인
        unmapped = df[df["Korean_Name"] == df["Institution"]]
        if not unmapped.empty:
            print(f"매핑 실패 대학 수: {len(unmapped)}")
            print("다음 대학명은 매핑표에 없습니다:")
            for name in sorted(unmapped["Institution"].unique()):
                print(f"   - {name}")

        # 중복된 국문 대학명 검사
        dup_korean = df["Korean_Name"].value_counts()
        duplicated_korean = dup_korean[dup_korean > 1]
        if not duplicated_korean.empty:
            print(f"중복된 국문 대학명 수: {len(duplicated_korean)}")
            print("복수 영문명이 동일 국문으로 매핑됨:")
            for name, count in duplicated_korean.items():
                matched_eng = df[df["Korean_Name"] == name]["Institution"].unique()
                print(f"   - {name} ({count}건): {list(matched_eng)}")

        # 매핑 무결성 검사: 동일 영문 → 복수 국문 (이상 상황 탐지)
        mapping_df = df[df["Korean_Name"] != df["Institution"]] \
                        .groupby("Institution")["Korean_Name"].nunique()
        invalid_mappings = mapping_df[mapping_df > 1]
        if not invalid_mappings.empty:
            print("매핑 오류: 하나의 영문명이 복수 국문으로 연결됨")
            for name in invalid_mappings.index:
                mapped_vals = df[df["Institution"] == name]["Korean_Name"].unique()
                print(f"   - {name} → {list(mapped_vals)}")

        # 저장
        df.to_csv(self.output_path, index=False, encoding="utf-8-sig")
        print(f"맵핑된 대학명 CSV 저장 완료: {self.output_path}")