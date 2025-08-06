import os
import cx_Oracle
from datetime import datetime
from dotenv import load_dotenv

# 1. 환경변수 로딩
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

ORACLE_USER = os.getenv('ORACLE_USER')
ORACLE_PASSWORD = os.getenv('ORACLE_PASSWORD')
ORACLE_DSN = os.getenv('ORACLE_DSN')
ORACLE_CLIENT_PATH = os.getenv('ORACLE_CLIENT_PATH')

# 2. 오라클 클라이언트 초기화
cx_Oracle.init_oracle_client(lib_dir=ORACLE_CLIENT_PATH)

# 3. DB 연결
conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)
cursor = conn.cursor()

# 4. 테이블 생성 쿼리
create_table_sql = """
BEGIN
    EXECUTE IMMEDIATE '
    CREATE TABLE USER_DATA (
        ID NUMBER PRIMARY KEY,
        USR_CR DATE NOT NULL,
        USR_ID VARCHAR2(50) UNIQUE NOT NULL,
        USR_PW VARCHAR2(128) NOT NULL,
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

# 5. 시퀀스 생성 쿼리
create_sequence_sql = """
BEGIN
    EXECUTE IMMEDIATE 'CREATE SEQUENCE USER_DATA_SEQ START WITH 1 INCREMENT BY 1';
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
"""

# 6. 관리자 계정 삽입 쿼리
insert_admin_sql = """
BEGIN
    INSERT INTO USER_DATA (
        ID, USR_CR, USR_ID, USR_PW, USR_NAME
    ) VALUES (
        USER_DATA_SEQ.NEXTVAL,
        :usr_cr,
        'libra_admin',
        '1234',
        '관리자'
    );
EXCEPTION
    WHEN DUP_VAL_ON_INDEX THEN
        NULL;
END;
"""

# 7. 실행
try:
    cursor.execute(create_table_sql)
    cursor.execute(create_sequence_sql)
    cursor.execute(insert_admin_sql, usr_cr=datetime.now())
    conn.commit()
    print("✅ 테이블, 시퀀스, 관리자 계정 생성 완료")
except Exception as e:
    print("❌ 오류 발생:", e)
finally:
    cursor.close()
    conn.close()
