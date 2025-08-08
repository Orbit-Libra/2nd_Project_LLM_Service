# web_frontend/api/register_api.py
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from .oracle_utils import get_connection  # 경로/대소문자 주의
import cx_Oracle

bp_register = Blueprint('bp_register', __name__)

# 1) 소속대학(SNM) 목록
@bp_register.get('/api/snm')
def api_snm():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT SNM FROM ESTIMATIONFUTURE ORDER BY SNM")
        items = [row[0] for row in cur.fetchall() if row and row[0]]
        return jsonify(success=True, items=items)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

# 2) 아이디 중복 체크
@bp_register.get('/api/check_id')
def api_check_id():
    usr_id = request.args.get('usr_id', '').strip()
    if not usr_id:
        return jsonify(error='usr_id is required'), 400
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 디버그 (유지해도 OK)
        cur.execute("SELECT SYS_CONTEXT('USERENV','SESSION_USER'), SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM DUAL")
        print("[DBG] SESSION_USER, CURRENT_SCHEMA =", cur.fetchone())
        cur.execute("SELECT OWNER, TABLE_NAME FROM ALL_TABLES WHERE TABLE_NAME='USER_DATA'")
        print("[DBG] ALL_TABLES USER_DATA =", cur.fetchall())

        # ★ 여기: 이름 바인드 -> 포지셔널 바인드
        cur.execute("SELECT COUNT(*) FROM USER_DATA WHERE USR_ID = :1", [usr_id])
        cnt = cur.fetchone()[0]
        return jsonify(exists=(cnt > 0))

    except Exception as e:
        print("[ERR]/api/check_id:", repr(e))
        return jsonify(error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

# 3) 회원가입 처리
@bp_register.post('/api/register')
def api_register():
    data = request.get_json(silent=True) or {}
    required = ['usr_id', 'usr_pw', 'usr_name', 'usr_email', 'usr_snm']
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify(success=False, error=f"필수 항목 누락: {', '.join(missing)}"), 400

    # 여기서 먼저 변수에 할당
    usr_id = data['usr_id'].strip()
    usr_pw = data['usr_pw']
    usr_name = data['usr_name'].strip()
    usr_email = data['usr_email'].strip()
    usr_snm = data['usr_snm'].strip()

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # (1) 아이디 중복 재확인
        cur.execute("SELECT COUNT(*) FROM USER_DATA WHERE USR_ID = :1", [usr_id])
        if cur.fetchone()[0] > 0:
            return jsonify(success=False, error='이미 사용 중인 아이디입니다.'), 409

        # (2) 소속대학 유효성 재확인
        cur.execute("SELECT COUNT(*) FROM ESTIMATIONFUTURE WHERE SNM = :1", [usr_snm])
        if cur.fetchone()[0] == 0:
            return jsonify(success=False, error='소속대학명이 목록과 일치하지 않습니다.'), 400

        # (3) 비밀번호 해시
        pw_hash = generate_password_hash(usr_pw)

        # (4) INSERT
        insert_sql = """
            INSERT INTO USER_DATA 
            (ID, USR_CR, USR_ID, USR_PW, USR_NAME, USR_EMAIL, USR_SNM)
            VALUES (USER_DATA_SEQ.NEXTVAL, SYSDATE, :1, :2, :3, :4, :5)
        """
        cur.execute(insert_sql, [usr_id, pw_hash, usr_name, usr_email, usr_snm])
        conn.commit()

        return jsonify(success=True)
    except cx_Oracle.DatabaseError as e:
        print("[DBERR]/api/register:", repr(e))
        return jsonify(success=False, error=str(e)), 500
    except Exception as e:
        print("[ERR]/api/register:", repr(e))
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()
