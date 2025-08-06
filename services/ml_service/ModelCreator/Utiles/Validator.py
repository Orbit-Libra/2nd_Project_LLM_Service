def validate_columns(df, required: list):
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"[ERROR] 누락된 컬럼: {missing}")
