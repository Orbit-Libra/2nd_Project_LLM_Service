#services\user_service\login_manager.py
import os
import cx_Oracle
from dotenv import load_dotenv
from werkzeug.security import check_password_hash  # ✅ 추가

# .env 로드
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.env'))
load_dotenv(dotenv_path=env_path, override=True)

# Oracle Instant Client 경로 설정 (Windows)
client_path = os.getenv("ORACLE_CLIENT_PATH")
if client_path:
    os.environ["PATH"] = client_path + ";" + os.environ.get("PATH", "")
else:
    print("[경고] ORACLE_CLIENT_PATH가 .env에서 로딩되지 않았습니다.")

def authenticate_user(usr_id: str, usr_pw: str) -> bool:
    conn = None
    cursor = None
    try:
        dsn = os.getenv("ORACLE_DSN")      # 예: localhost:1521/XE
        user = os.getenv("ORACLE_USER")
        password = os.getenv("ORACLE_PASSWORD")

        if not all([dsn, user, password]):
            print("[오류] .env에서 Oracle 접속 정보가 누락되었습니다.")
            return False

        conn = cx_Oracle.connect(user=user, password=password, dsn=dsn)
        cursor = conn.cursor()

        # ✅ 저장된 해시만 조회 (포지셔널 바인드)
        cursor.execute(
            "SELECT USR_PW FROM USER_DATA WHERE USR_ID = :1",
            [usr_id]
        )
        row = cursor.fetchone()
        if not row:
            return False

        stored_hash = row[0]
        # ✅ 해시 검증
        return check_password_hash(stored_hash, usr_pw)

    except Exception as e:
        print(f"[로그인 오류] {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
