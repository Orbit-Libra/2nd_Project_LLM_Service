#services\user_service\init_oracle_user_data.py
import os
import cx_Oracle
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# 1) .env 로드
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

# 2) 오라클 클라이언트 초기화
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
#    PK/UK 이름을 명시하여 안정화
create_table_sql = """
BEGIN
  EXECUTE IMMEDIATE '
    CREATE TABLE USER_DATA (
        ID        NUMBER        NOT NULL,
        USR_CR    DATE          NOT NULL,
        USR_ID    VARCHAR2(50)  NOT NULL,
        USR_PW    VARCHAR2(255) NOT NULL,
        USR_NAME  VARCHAR2(50)  NOT NULL,
        USR_EMAIL VARCHAR2(120),
        USR_SNM   VARCHAR2(100),
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
        SCR_EST_4TH NUMBER,
        CONSTRAINT PK_USER_DATA          PRIMARY KEY (ID),
        CONSTRAINT UK_USER_DATA_USR_ID   UNIQUE (USR_ID)
    )';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
"""

create_sequence_sql = """
BEGIN
  EXECUTE IMMEDIATE 'CREATE SEQUENCE USER_DATA_SEQ START WITH 1 INCREMENT BY 1';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
"""

insert_admin_sql = """
DECLARE
  v_exists NUMBER := 0;
BEGIN
  SELECT COUNT(*) INTO v_exists FROM USER_DATA WHERE USR_ID = 'libra_admin';
  IF v_exists = 0 THEN
    INSERT INTO USER_DATA (ID, USR_CR, USR_ID, USR_PW, USR_NAME)
    VALUES (USER_DATA_SEQ.NEXTVAL, :1, 'libra_admin', :2, '관리자');
  END IF;
END;
"""

try:
    cursor.execute(create_table_sql)
    cursor.execute(create_sequence_sql)

    admin_plain = os.getenv("ADMIN_INIT_PASSWORD", "1234")
    admin_hash = generate_password_hash(admin_plain)

    cursor.execute(insert_admin_sql, [datetime.now(), admin_hash])

    conn.commit()
    print("✅ USER_DATA 테이블/시퀀스/관리자 계정 생성 완료")
except Exception as e:
    print("❌ 오류 발생:", e)
    conn.rollback()
    raise
finally:
    cursor.close()
    conn.close()
