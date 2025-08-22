# -*- coding: utf-8 -*-
import os
import cx_Oracle
from dotenv import load_dotenv

# 1) .env 로드
here = os.path.dirname(os.path.abspath(__file__))
candidate_env_paths = [
    os.path.join(here, ".env"),
    os.path.abspath(os.path.join(here, "..", ".env")),
    os.path.abspath(os.path.join(here, "..", "..", ".env")),
]
env_path = next((p for p in candidate_env_paths if os.path.exists(p)), None)
if env_path:
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"[INFO] .env 로드: {env_path}")
else:
    print("[경고] .env를 찾지 못했습니다. 환경변수를 직접 사용합니다.")

ORACLE_USER = os.getenv("ORACLE_USER", "LIBRA_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "1234")
ORACLE_DSN = os.getenv("ORACLE_DSN", "localhost:1521/XE")
ORACLE_CLIENT_PATH = os.getenv("ORACLE_CLIENT_PATH")

# 2) Instant Client 초기화
if ORACLE_CLIENT_PATH:
    try:
        cx_Oracle.init_oracle_client(lib_dir=ORACLE_CLIENT_PATH)
    except cx_Oracle.ProgrammingError as e:
        if "already been initialized" in str(e):
            pass
        else:
            raise
else:
    print("[경고] ORACLE_CLIENT_PATH 미설정. SQL*Net이 PATH에 잡혀있어야 합니다.")

# 3) 연결
conn = cx_Oracle.connect(
    user=ORACLE_USER,
    password=ORACLE_PASSWORD,
    dsn=ORACLE_DSN,
    encoding="UTF-8",
    nencoding="UTF-8",
)
cur = conn.cursor()

# 4) 객체 생성 (있으면 스킵)
#    USER_DATA.USR_ID (VARCHAR2(50))를 참조한다고 가정
create_table_sql = """
BEGIN
  EXECUTE IMMEDIATE '
    CREATE TABLE LLM_DATA (
      CONV_ID               NUMBER       NOT NULL,
      USR_ID                VARCHAR2(50) NOT NULL,
      MSG_ID                NUMBER       NOT NULL,
      ROLE                  VARCHAR2(16) CHECK (ROLE IN (''user'',''assistant'',''system'',''summary'')) NOT NULL,
      CONTENT               CLOB         NOT NULL,
      TOKENS                NUMBER       DEFAULT 0,
      SUMMARY               CLOB         NULL,
      SUMMARY_UP_TO_MSG_ID  NUMBER       NULL,
      CREATED_AT            TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL,
      CONSTRAINT PK_LLM_DATA PRIMARY KEY (CONV_ID, MSG_ID)
    )';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
"""


create_or_fix_fk_sql = """
DECLARE
  v_fk_exists    NUMBER := 0;
  v_delete_rule  VARCHAR2(10);
BEGIN
  SELECT COUNT(*)
    INTO v_fk_exists
    FROM user_constraints
   WHERE table_name      = 'LLM_DATA'
     AND constraint_name = 'FK_LLM_DATA_USER'
     AND constraint_type = 'R';

  IF v_fk_exists = 1 THEN
    SELECT delete_rule
      INTO v_delete_rule
      FROM user_constraints
     WHERE table_name      = 'LLM_DATA'
       AND constraint_name = 'FK_LLM_DATA_USER'
       AND constraint_type = 'R';

    IF v_delete_rule <> 'CASCADE' THEN
      EXECUTE IMMEDIATE 'ALTER TABLE LLM_DATA DROP CONSTRAINT FK_LLM_DATA_USER';
      EXECUTE IMMEDIATE '
        ALTER TABLE LLM_DATA
          ADD CONSTRAINT FK_LLM_DATA_USER
          FOREIGN KEY (USR_ID)
          REFERENCES USER_DATA(USR_ID)
          ON DELETE CASCADE
      ';
    END IF;
  ELSE
    EXECUTE IMMEDIATE '
      ALTER TABLE LLM_DATA
        ADD CONSTRAINT FK_LLM_DATA_USER
        FOREIGN KEY (USR_ID)
        REFERENCES USER_DATA(USR_ID)
        ON DELETE CASCADE
    ';
  END IF;
END;
"""

# 인덱스 (USR_ID, CREATED_AT DESC)
create_index_sql = """
BEGIN
  EXECUTE IMMEDIATE 'CREATE INDEX IX_LLM_USER_UPDATED ON LLM_DATA (USR_ID, CREATED_AT DESC)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
"""

create_seq_conv_sql = """
BEGIN
  EXECUTE IMMEDIATE 'CREATE SEQUENCE SEQ_LLM_CONV START WITH 1 INCREMENT BY 1 NOCACHE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
"""

create_seq_msg_sql = """
BEGIN
  EXECUTE IMMEDIATE 'CREATE SEQUENCE SEQ_LLM_MSG START WITH 1 INCREMENT BY 1 NOCACHE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -955 THEN
      RAISE;
    END IF;
END;
"""

try:
    cur.execute(create_table_sql)
    print("✅ LLM_DATA 테이블 준비 완료(있으면 스킵).")

    # FK: ON DELETE CASCADE 보장
    cur.execute(create_or_fix_fk_sql)
    print("✅ FK_LLM_DATA_USER(CASCADE) 적용/수정 완료.")

    # 인덱스
    cur.execute(create_index_sql)
    print("✅ IX_LLM_USER_UPDATED 인덱스 준비 완료(있으면 스킵).")

    # 시퀀스
    cur.execute(create_seq_conv_sql)
    cur.execute(create_seq_msg_sql)
    print("✅ 시퀀스 SEQ_LLM_CONV / SEQ_LLM_MSG 준비 완료(있으면 스킵).")

    conn.commit()
    print("🎉 멀티턴용 LLM_DATA 초기화 완료.")
except Exception as e:
    print("❌ 오류 발생:", e)
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
