import pandas as pd
from core_utiles.OracleSchemaBuilder import OSB

def OTC(cursor, table_name: str, df: pd.DataFrame):
    # 기존 테이블 제거
    try:
        cursor.execute(f'DROP TABLE "{table_name}"')
    except Exception:
        pass  # 존재하지 않으면 무시

    # 컬럼별 타입 추론 후 테이블 생성
    col_defs = OSB(df)
    create_sql = f'CREATE TABLE "{table_name}" ({col_defs})'
    cursor.execute(create_sql)