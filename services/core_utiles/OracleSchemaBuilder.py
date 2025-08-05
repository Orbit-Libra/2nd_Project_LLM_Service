# core_utiles/OracleSchemaBuilder.py
import pandas as pd
import re

def OSB(df: pd.DataFrame, varchar_len: int = 4000) -> str:
    """
    Oracle 테이블 생성용 컬럼 정의 문자열 반환.
    - 숫자만 포함 → INT or FLOAT
    - 한글/영문 혼합 → VARCHAR2
    """
    col_defs = []

    for col in df.columns:
        series = df[col].dropna().astype(str)

        # 샘플 상위 10개만 기반으로 판단
        samples = series.head(10)
        result_type = "VARCHAR2"

        is_numeric = True
        has_float = False
        has_alpha = False

        for val in samples:
            val = val.strip()

            if re.search(r'[ㄱ-ㅎ가-힣a-zA-Z]', val):
                has_alpha = True
                break  # 문자 있음 → VARCHAR2 결정

            if re.fullmatch(r'[-+]?\d+', val):
                continue  # 정수
            elif re.fullmatch(r'[-+]?\d*\.\d+', val):
                has_float = True  # 실수
            else:
                is_numeric = False
                break

        if has_alpha:
            result_type = f'VARCHAR2({varchar_len})'
        elif is_numeric:
            result_type = 'FLOAT' if has_float else 'INT'
        else:
            result_type = f'VARCHAR2({varchar_len})'

        col_defs.append(f'"{col}" {result_type}')

    return ', '.join(col_defs)