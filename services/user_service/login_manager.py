import cx_Oracle
import os
from dotenv import load_dotenv

# 절대경로로 .env 로딩
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.env'))
load_dotenv(dotenv_path=env_path)

# 디버깅: 환경변수 확인
client_path = os.getenv("ORACLE_CLIENT_PATH")

# Oracle Instant Client 경로 설정 (Windows 환경)
if client_path:
    os.environ["PATH"] = client_path + ";" + os.environ.get("PATH", "")
else:
    print("[경고] ORACLE_CLIENT_PATH가 .env에서 로딩되지 않았습니다.")

def authenticate_user(usr_id, usr_pw):
    try:
        dsn = os.getenv("ORACLE_DSN")  # 예: localhost:1521/XE
        user = os.getenv("ORACLE_USER")
        password = os.getenv("ORACLE_PASSWORD")

        if not all([dsn, user, password]):
            print("[오류] .env에서 Oracle 접속 정보가 누락되었습니다.")
            return False

        conn = cx_Oracle.connect(user=user, password=password, dsn=dsn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM USER_DATA 
            WHERE usr_id = :id AND usr_pw = :pw
        """, id=usr_id, pw=usr_pw)
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return result == 1
    except Exception as e:
        print(f"[로그인 오류] {e}")
        return False
