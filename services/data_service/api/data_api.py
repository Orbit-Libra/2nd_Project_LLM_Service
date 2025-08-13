import os
import cx_Oracle
from flask import Blueprint, jsonify
from dotenv import load_dotenv

# .env 로드
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv(dotenv_path=env_path)

# Oracle Instant Client 초기화
oracle_client_path = os.getenv("ORACLE_CLIENT_PATH")
if oracle_client_path and os.path.exists(oracle_client_path):
    os.environ["PATH"] = oracle_client_path + ";" + os.environ["PATH"]
    cx_Oracle.init_oracle_client(lib_dir=oracle_client_path)
else:
    print("⚠️ ORACLE_CLIENT_PATH가 존재하지 않거나 잘못되었습니다.")

# Blueprint 생성
data_api = Blueprint('data_api', __name__)

@data_api.route('/api/get-estimationfuture', methods=['GET'])
def get_estimationfuture():
    # Oracle 접속 정보 로드
    ORACLE_USER = os.getenv("ORACLE_USER")
    ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
    ORACLE_DSN = os.getenv("ORACLE_DSN")

    if not all([ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN]):
        return jsonify({'error': 'DB 접속 정보가 .env에 없습니다.'})

    # Oracle 연결
    try:
        conn = cx_Oracle.connect(ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN)
        cursor = conn.cursor()

        # 쿼리 실행
        cursor.execute("SELECT * FROM ESTIMATIONFUTURE")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        # 결과 변환
        result = [dict(zip(columns, row)) for row in rows]
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Oracle 연결 실패: {str(e)}'})
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass
