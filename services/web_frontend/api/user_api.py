# services/web_frontend/api/user_api.py
from flask import Blueprint, request, jsonify, session
from .oracle_utils import get_connection
import cx_Oracle

bp_user = Blueprint('bp_user', __name__)

def _num(v):
    # JSON에서 None/'' 처리 → None, 숫자면 float/int 허용
    if v is None: return None
    if isinstance(v, (int, float)): return v
    try:
        s = str(v).strip()
        return None if s == '' else float(s)
    except Exception:
        return None

@bp_user.post('/api/user/academic')
def save_academic():
    # 로그인 확인
    usr_id = session.get('user')
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    data = request.get_json(silent=True) or {}

    # 바인드 값 준비 (포지셔널 바인드, 숫자 또는 None)
    p = [
        _num(data.get('1ST_YR')),
        _num(data.get('1ST_USR_CPS')),
        _num(data.get('1ST_USR_LPS')),
        _num(data.get('1ST_USR_VPS')),
        _num(data.get('2ND_YR')),
        _num(data.get('2ND_USR_CPS')),
        _num(data.get('2ND_USR_LPS')),
        _num(data.get('2ND_USR_VPS')),
        _num(data.get('3RD_YR')),
        _num(data.get('3RD_USR_CPS')),
        _num(data.get('3RD_USR_LPS')),
        _num(data.get('3RD_USR_VPS')),
        _num(data.get('4TH_YR')),
        _num(data.get('4TH_USR_CPS')),
        _num(data.get('4TH_USR_LPS')),
        _num(data.get('4TH_USR_VPS')),
    ]

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # UPDATE (인용부호 필요한 컬럼 주의)
        sql = """
            UPDATE USER_DATA SET
                "1ST_YR"=:1, "1ST_USR_CPS"=:2, "1ST_USR_LPS"=:3, "1ST_USR_VPS"=:4,
                "2ND_YR"=:5, "2ND_USR_CPS"=:6, "2ND_USR_LPS"=:7, "2ND_USR_VPS"=:8,
                "3RD_YR"=:9, "3RD_USR_CPS"=:10, "3RD_USR_LPS"=:11, "3RD_USR_VPS"=:12,
                "4TH_YR"=:13, "4TH_USR_CPS"=:14, "4TH_USR_LPS"=:15, "4TH_USR_VPS"=:16
            WHERE USR_ID = :17
        """
        cur.execute(sql, p + [usr_id])
        conn.commit()
        return jsonify(success=True)
    except cx_Oracle.DatabaseError as e:
        return jsonify(success=False, error=str(e)), 500
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()
