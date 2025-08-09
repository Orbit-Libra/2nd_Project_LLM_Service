# services/web_frontend/api/profile_api.py
from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash
from .oracle_utils import get_connection
import cx_Oracle

bp_profile = Blueprint('bp_profile', __name__)

def _require_login():
    usr_id = session.get('user')
    if not usr_id:
        return None, (jsonify(success=False, error='로그인이 필요합니다.'), 401)
    return usr_id, None

@bp_profile.put('/api/user/profile')
def update_profile():
    # 로그인 확인
    usr_id, err = _require_login()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    usr_name = (data.get('usr_name') or '').strip()
    usr_email = (data.get('usr_email') or '').strip()
    usr_snm = (data.get('usr_snm') or '').strip()
    cur_pw = data.get('current_password') or ''
    new_pw = data.get('new_password') or None

    if not (usr_name and usr_email and usr_snm and cur_pw):
        return jsonify(success=False, error='필수 항목 누락'), 400

    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 1) 현재 비밀번호 해시 조회
        cur.execute("SELECT USR_PW FROM USER_DATA WHERE USR_ID = :1", [usr_id])
        row = cur.fetchone()
        if not row:
            return jsonify(success=False, error='사용자 정보를 찾을 수 없습니다.'), 404

        pw_hash = row[0]
        if not check_password_hash(pw_hash, cur_pw):
            return jsonify(success=False, error='현재 비밀번호가 올바르지 않습니다.'), 401

        # 2) 소속대학 유효성 검사
        cur.execute("SELECT COUNT(*) FROM ESTIMATIONFUTURE WHERE SNM = :1", [usr_snm])
        if cur.fetchone()[0] == 0:
            return jsonify(success=False, error='소속대학명이 목록과 일치하지 않습니다.'), 400

        # 3) UPDATE
        if new_pw:
            new_hash = generate_password_hash(new_pw)
            sql = """
                UPDATE USER_DATA
                   SET USR_NAME = :1,
                       USR_EMAIL = :2,
                       USR_SNM = :3,
                       USR_PW = :4
                 WHERE USR_ID = :5
            """
            params = [usr_name, usr_email, usr_snm, new_hash, usr_id]
        else:
            sql = """
                UPDATE USER_DATA
                   SET USR_NAME = :1,
                       USR_EMAIL = :2,
                       USR_SNM = :3
                 WHERE USR_ID = :4
            """
            params = [usr_name, usr_email, usr_snm, usr_id]

        cur.execute(sql, params)
        if cur.rowcount == 0:
            return jsonify(success=False, error='변경사항이 적용되지 않았습니다.'), 400

        conn.commit()
        return jsonify(success=True)

    except cx_Oracle.DatabaseError as e:
        print("[DBERR]/api/user/profile:", repr(e))
        return jsonify(success=False, error='데이터베이스 오류'), 500
    except Exception as e:
        print("[ERR]/api/user/profile:", repr(e))
        return jsonify(success=False, error=str(e)), 500
    finally:
        try:
            cur and cur.close()
        finally:
            conn and conn.close()
