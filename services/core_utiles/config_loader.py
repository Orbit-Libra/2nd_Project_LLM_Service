import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), "..", "_Configs", ".env")
load_dotenv(dotenv_path=env_path)


ORACLE_USER         = os.getenv("ORACLE_USER")
ORACLE_PASSWORD     = os.getenv("ORACLE_PASSWORD")
ORACLE_DSN          = os.getenv("ORACLE_DSN")
ORACLE_CLIENT_PATH  = os.getenv("ORACLE_CLIENT_PATH")

BASE_RAW_DIR        = os.getenv("BASE_RAW_DIR")
BASE_CSV_DIR        = os.getenv("BASE_CSV_DIR")
BASE_OUTPUT_DIR     = os.getenv("BASE_OUTPUT_DIR")

CSV_NUM06_PREFIX    = os.getenv("CSV_NUM06_PREFIX")
CSV_NUM07_PREFIX    = os.getenv("CSV_NUM07_PREFIX")
CSV_FILTERED_PREFIX = os.getenv("CSV_FILTERED_PREFIX")

RFR_SAVE_PATH = os.getenv("RFR_SAVE_PATH")
SCALER_NUM01_SAVE_PATH = os.getenv("SCALER_NUM01_SAVE_PATH")
CLUSTER_NUM01_SAVE_PATH = os.getenv("CLUSTER_NUM01_SAVE_PATH")

CSV_NUM08_PREFIX = os.getenv("CSV_NUM08_PREFIX")

MODEL_NUM02_SAVE_PATH = os.getenv("MODEL_NUM02_SAVE_PATH")
SCALER_NUM02_SAVE_PATH = os.getenv("SCALER_NUM02_SAVE_PATH")

CSV_NUM09_PREFIX = os.getenv("CSV_NUM09_PREFIX")

RFR_CONFIG_PATH = os.getenv("RFR_CONFIG_PATH")
RFR_METRICS_PATH = os.getenv("RFR_METRICS_PATH")

MODEL_SAVE_PATH = os.getenv("MODEL_SAVE_PATH")
LOG_SAVE_PATH = os.getenv("LOG_SAVE_PATH")

RAW_DATA_RANGE = os.getenv("RAW_DATA_RANGE")

def get_raw_years() -> list[int]:
    try:
        clean = RAW_DATA_RANGE.strip("[]").replace(" ", "")
        start, end = map(int, clean.split(":"))
        return list(range(start, end + 1))
    except Exception as e:
        print(f"[경고] RAW_DATA_RANGE 파싱 실패 ➜ {e}")
        return []