import os
import cx_Oracle
from dotenv import load_dotenv

# 절대 경로로 .env 로딩
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../user_service/.env'))
load_dotenv(dotenv_path=env_path, override=True)

# Oracle Instant Client 경로 설정
client_path = os.getenv("ORACLE_CLIENT_PATH")
if client_path:
    os.environ["PATH"] = client_path + ";" + os.environ.get("PATH", "")
else:
    print("[경고] ORACLE_CLIENT_PATH가 .env에서 로딩되지 않았습니다.")

# 전역 초기화 상태 추적
_oracle_client_initialized = False

def initialize_oracle_client():
    global _oracle_client_initialized

    if _oracle_client_initialized:
        return True

    try:
        if client_path and os.path.exists(client_path):
            try:
                cx_Oracle.init_oracle_client(lib_dir=client_path)
                _oracle_client_initialized = True
                print("Oracle Client 초기화 성공")
                return True
            except cx_Oracle.ProgrammingError as e:
                if "has already been initialized" in str(e):
                    _oracle_client_initialized = True
                    return True
                else:
                    print(f"Oracle Client 초기화 실패: {e}")
                    return False
        else:
            print("[경고] Oracle Client 경로가 존재하지 않거나 설정되지 않았습니다.")
            _oracle_client_initialized = True
            return True
    except Exception as e:
        print(f"[오류] Oracle Client 초기화 중 예외 발생: {e}")
        return False

def get_connection():
    if not initialize_oracle_client():
        raise Exception("Oracle Client 초기화 실패")

    try:
        user = os.getenv("ORACLE_USER")
        password = os.getenv("ORACLE_PASSWORD")
        dsn = os.getenv("ORACLE_DSN")

        if not all([user, password, dsn]):
            missing = []
            if not user: missing.append("ORACLE_USER")
            if not password: missing.append("ORACLE_PASSWORD")
            if not dsn: missing.append("ORACLE_DSN")
            raise Exception(f"[환경 변수 누락] {', '.join(missing)}")

        print(f"[Oracle 연결 시도] {user}@{dsn}")
        conn = cx_Oracle.connect(user=user, password=password, dsn=dsn)
        print("[Oracle 연결 성공]")
        return conn
    except Exception as e:
        print(f"[Oracle 연결 오류] {e}")
        raise

def test_connection():
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        result = cursor.fetchone()
        cursor.close()
        return True, "연결 성공"
    except Exception as e:
        return False, str(e)
    finally:
        if connection:
            connection.close()

def get_table_data(table_name, limit=None):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = '{table_name.upper()}'")
        if cursor.fetchone()[0] == 0:
            raise Exception(f"테이블 '{table_name}'이 존재하지 않습니다.")

        cursor.execute(f"""
            SELECT COLUMN_NAME FROM USER_TAB_COLUMNS 
            WHERE TABLE_NAME = '{table_name.upper()}' 
            ORDER BY COLUMN_ID
        """)
        columns = [row[0] for row in cursor.fetchall()]

        query = f"SELECT * FROM {table_name}"
        if limit:
            query = f"SELECT * FROM {table_name} WHERE ROWNUM <= {limit}"
        query += " ORDER BY 1"

        cursor.execute(query)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                if value is None:
                    row_dict[columns[i]] = None
                elif isinstance(value, (int, float)):
                    row_dict[columns[i]] = float(value)
                elif hasattr(value, 'read'):
                    row_dict[columns[i]] = str(value.read())
                else:
                    row_dict[columns[i]] = str(value).strip()
            data.append(row_dict)

        return {
            'success': True,
            'data': data,
            'columns': columns,
            'count': len(data)
        }

    except Exception as e:
        print(f"[테이블 조회 오류] {str(e)}")
        return {
            
            'success': False,
            'error': str(e),
            'data': [],
            'columns': []
        }

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
