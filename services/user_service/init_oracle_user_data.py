import os
import cx_Oracle
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# 1) .env 로드 (services/user_service/.env 우선)
here = os.path.dirname(os.path.abspath(__file__))
candidate_env_paths = [
    os.path.join(here, '.env'),
    os.path.abspath(os.path.join(here, '..', 'services', 'user_service', '.env')),
    os.path.abspath(os.path.join(here, '..', 'user_service', '.env')),
    os.path.abspath(os.path.join(here, '..', '..', 'services', 'user_service', '.env')),
]

env_path = next((p for p in candidate_env_paths if os.path.exists(p)), None)
if env_path:
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"[INFO] .env 로드: {env_path}")
else:
    print("[경고] services/user_service/.env 파일을 찾지 못했습니다. 기본 환경변수를 사용합니다.")

ORACLE_USER = os.getenv('ORACLE_USER')
ORACLE_PASSWORD = os.getenv('ORACLE_PASSWORD')
ORACLE_DSN = os.getenv('ORACLE_DSN')
ORACLE_CLIENT_PATH = os.getenv('ORACLE_CLIENT_PATH')

# 2) 오라클 클라이언트 초기화 (이미 초기화된 경우 무시)
if ORACLE_CLIENT_PATH:
    try:
        cx_Oracle.init_oracle_client(lib_dir=ORACLE_CLIENT_PATH)
    except cx_Oracle.ProgrammingError as e:
        if "already been initialized" in str(e):
            pass
        else:
            raise
else:
    print("[경고] ORACLE_CLIENT_PATH가 설정되지 않았습니다. 환경 변수를 확인하세요.")

# 3) DB 연결
conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)
cursor = conn.cursor()

# 4) 테이블 & 시퀀스 & 관리자 계정 생성
create_table_sql = """
BEGIN
    EXECUTE IMMEDIATE '
    CREATE TABLE USER_DATA (
        ID NUMBER PRIMARY KEY,
        USR_CR DATE NOT NULL,
        USR_ID VARCHAR2(50) UNIQUE NOT NULL,
        USR_PW VARCHAR2(255) NOT NULL,
        USR_NAME VARCHAR2(50) NOT NULL,
        USR_EMAIL VARCHAR2(120),
        USR_SNM VARCHAR2(100),
        "1ST_YR" NUMBER,
        "1ST_USR_CPS" NUMBER,
        "1ST_USR_LPS" NUMBER,
        "1ST_USR_VPS" NUMBER,
        "2ND_YR" NUMBER,
        "2ND_USR_CPS" NUMBER,
        "2ND_USR_LPS" NUMBER,
        "2ND_USR_VPS" NUMBER,
        "3RD_YR" NUMBER,
        "3RD_USR_CPS" NUMBER,
        "3RD_USR_LPS" NUMBER,
        "3RD_USR_VPS" NUMBER,
        "4TH_YR" NUMBER,
        "4TH_USR_CPS" NUMBER,
        "4TH_USR_LPS" NUMBER,
        "4TH_USR_VPS" NUMBER,
        SCR_EST_1ST NUMBER,
        SCR_EST_2ND NUMBER,
        SCR_EST_3RD NUMBER,
        SCR_EST_4TH NUMBER
    )';
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
"""

create_sequence_sql = """
BEGIN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE USER_DATA_SEQ START WITH 1 INCREMENT BY 1';
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
"""

insert_admin_sql = """
BEGIN
    INSERT INTO USER_DATA (
        ID, USR_CR, USR_ID, USR_PW, USR_NAME
    ) VALUES (
        USER_DATA_SEQ.NEXTVAL,
        :1,             -- USR_CR
        'libra_admin',  -- USR_ID
        :2,             -- USR_PW (해시)
        '관리자'         -- USR_NAME
    );
EXCEPTION
    WHEN DUP_VAL_ON_INDEX THEN
        NULL;
END;
"""

try:
    cursor.execute(create_table_sql)
    cursor.execute(create_sequence_sql)

    admin_plain = os.getenv("ADMIN_INIT_PASSWORD", "1234")
    admin_hash = generate_password_hash(admin_plain)

    cursor.execute(insert_admin_sql, [datetime.now(), admin_hash])

    conn.commit()
    print("✅ 테이블, 시퀀스, 관리자 계정 생성 완료 (비밀번호 해시 저장)")
except Exception as e:
    print("❌ 오류 발생:", e)
finally:
    cursor.close()
    conn.close()
