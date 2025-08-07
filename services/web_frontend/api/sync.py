import os
import re
import requests
import pandas as pd
import cx_Oracle
from flask import Blueprint, jsonify
from dotenv import load_dotenv

# .env 로드
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
env_path = os.path.join(BASE_DIR, 'web_frontend', '.env')
load_dotenv(dotenv_path=env_path)

# Oracle Instant Client 초기화
oracle_client_path = os.getenv("ORACLE_CLIENT_PATH")
if oracle_client_path and os.path.exists(oracle_client_path):
    os.environ["PATH"] = oracle_client_path + ";" + os.environ["PATH"]
    cx_Oracle.init_oracle_client(lib_dir=oracle_client_path)

sync_bp = Blueprint('sync_api', __name__)

def sanitize_column(col):
    """컬럼명 정제"""
    col = col.strip().replace(" ", "_").replace("-", "_").replace(".", "_")
    col = re.sub(r'[^A-Za-z0-9_]', '', col)
    if col and col[0].isdigit():
        col = "_" + col
    return col.upper()

def infer_column_types(df):
    """컬럼별 데이터 타입 추론"""
    types = {}
    for col in df.columns:
        # 모든 값이 숫자형이면 NUMBER로 지정
        if pd.to_numeric(df[col], errors='coerce').notnull().all():
            types[col] = 'NUMBER'
        else:
            types[col] = 'VARCHAR2(4000)'
    return types

@sync_bp.route('/sync-estimation', methods=['POST'])
def sync_estimation():
    """libra_data → libra_web 스키마 동기화"""
    
    try:
        # 1. API에서 데이터 수신
        response = requests.get("http://localhost:5050/api/get-estimationfuture", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict) and 'error' in data:
            return jsonify({'message': f'data_service 에러: {data["error"]}'})
        
        if not data:
            return jsonify({'message': 'libra_data 스키마에 데이터가 없습니다.'})
        
        # 2. 데이터프레임 변환
        if isinstance(data, dict):
            data = [data]
        
        df = pd.DataFrame(data)
        df.columns = [sanitize_column(col) for col in df.columns]
        
        # 3. Oracle 연결 (환경변수 재로드)
        oracle_env_vars = ['ORACLE_USER', 'ORACLE_PASSWORD', 'ORACLE_DSN']
        for var in oracle_env_vars:
            if var in os.environ:
                del os.environ[var]
        
        load_dotenv(dotenv_path=env_path, override=True)
        
        ORACLE_USER = os.getenv("ORACLE_USER")
        ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
        ORACLE_DSN = os.getenv("ORACLE_DSN")
        
        if not all([ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN]):
            return jsonify({'message': 'Oracle 접속 정보 로드 실패'})
        
        conn = cx_Oracle.connect(ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN)
        cursor = conn.cursor()
        
        # 4. 테이블 재생성
        table_name = "ESTIMATIONFUTURE"
        
        # 기존 테이블 삭제
        try:
            cursor.execute(f'DROP TABLE {table_name}')
            conn.commit()
        except:
            pass  # 테이블이 없어도 계속 진행
        
        # 컬럼 타입 추론
        column_types = infer_column_types(df)
        column_defs = [f'{col} {column_types[col]}' for col in df.columns]
        create_sql = f'CREATE TABLE {table_name} ({", ".join(column_defs)})'
        cursor.execute(create_sql)
        conn.commit()
        
        # 5. 데이터 삽입
        column_names = df.columns.tolist()
        placeholders = ", ".join([f":{i+1}" for i in range(len(column_names))])
        insert_sql = f'INSERT INTO {table_name} ({", ".join(column_names)}) VALUES ({placeholders})'
        
        insert_count = 0
        for _, row in df.iterrows():
            values = []
            for col in column_names:
                val = row[col]
                if pd.isna(val):
                    values.append(None)
                elif column_types[col] == 'NUMBER':
                    try:
                        values.append(float(val))
                    except:
                        values.append(None)
                else:
                    values.append(str(val))
            try:
                cursor.execute(insert_sql, values)
                insert_count += 1
            except:
                continue
        
        conn.commit()
        
        # 6. 결과 확인
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        final_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT USER FROM DUAL")
        actual_user = cursor.fetchone()[0]
        
        return jsonify({
            'message': f'동기화 완료: {insert_count}행 처리',
            'target_schema': actual_user,
            'final_db_rows': final_count
        })
        
    except requests.exceptions.ConnectionError:
        return jsonify({'message': 'data_service API 서버 연결 실패 (http://localhost:5050)'})
    except Exception as e:
        return jsonify({'message': f'동기화 실패: {str(e)}'})
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

@sync_bp.route('/sync-status', methods=['GET'])
def sync_status():
    """동기화 상태 확인"""
    try:
        ORACLE_USER = os.getenv("ORACLE_USER")
        ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
        ORACLE_DSN = os.getenv("ORACLE_DSN")
        
        conn = cx_Oracle.connect(ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM user_tables WHERE table_name = 'ESTIMATIONFUTURE'")
        table_exists = cursor.fetchone()[0] > 0
        
        if table_exists:
            cursor.execute("SELECT COUNT(*) FROM ESTIMATIONFUTURE")
            row_count = cursor.fetchone()[0]
            return jsonify({'table_exists': True, 'row_count': row_count})
        else:
            return jsonify({'table_exists': False, 'row_count': 0})
            
    except Exception as e:
        return jsonify({'error': f'상태 확인 실패: {str(e)}'})
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass
