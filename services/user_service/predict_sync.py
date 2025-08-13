# services/user_service/predict_sync.py (최상위에 있다고 가정)
import os
import requests
from flask import Blueprint, request, jsonify, session
from services.web_frontend.api.oracle_utils import get_connection
import cx_Oracle

bp_predict_sync = Blueprint('bp_predict_sync', __name__, url_prefix='/api/user')

PREDICT_API_URL = os.getenv('PREDICT_API_URL', 'http://localhost:5100/predict/user')

USER_COLS = [
    'USR_SNM',
    '1ST_YR','1ST_USR_CPS','1ST_USR_LPS','1ST_USR_VPS',
    '2ND_YR','2ND_USR_CPS','2ND_USR_LPS','2ND_USR_VPS',
    '3RD_YR','3RD_USR_CPS','3RD_USR_LPS','3RD_USR_VPS',
    '4TH_YR','4TH_USR_CPS','4TH_USR_LPS','4TH_USR_VPS'
]

def _quote_col(col: str) -> str:
    return f'"{col}"' if col[0].isdigit() or not col.isidentifier() else col

@bp_predict_sync.post('/predict-sync')
def predict_and_save():
    usr_id = session.get('user')
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    conn = cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # ---------- SELECT (유저 데이터 읽기) ----------
        try:
            select_cols_sql = ','.join(_quote_col(c) for c in USER_COLS)
            sql_sel = f"SELECT {select_cols_sql} FROM USER_DATA WHERE USR_ID = :1"
            print("[DBG] SELECT SQL:", sql_sel)
            cur.execute(sql_sel, [usr_id])  # 포지셔널 바인딩
            row = cur.fetchone()
        except cx_Oracle.DatabaseError as e:
            print("[ERR] SELECT 실패:", e)
            return jsonify(success=False, error=f'DB SELECT 오류: {e}'), 500

        if not row:
            return jsonify(success=False, error='계정 정보를 찾을 수 없습니다.'), 404

        payload = {col: row[i] for i, col in enumerate(USER_COLS)}
        if not payload.get('USR_SNM'):
            return jsonify(success=False, error='소속대학이 등록되어 있지 않습니다.'), 400

        # ---------- 예측 서비스 호출 ----------
        try:
            res = requests.post(PREDICT_API_URL, json=payload, timeout=15)
        except requests.RequestException as e:
            return jsonify(success=False, error=f'예측 서비스 연결 실패: {e}'), 502

        if not res.ok:
            return jsonify(success=False, error=f'예측 서비스 오류: {res.text}'), 502

        body = res.json()
        if not body.get('success'):
            return jsonify(success=False, error=body.get('error', '예측 실패')), 502

        preds = body.get('predictions', {}) or {}

        # 값 정규화 (숫자/None만)
        def _num_or_none(v):
            if v is None: return None
            try:
                return float(v)
            except Exception:
                return None

        p1 = _num_or_none(preds.get('SCR_EST_1ST'))
        p2 = _num_or_none(preds.get('SCR_EST_2ND'))
        p3 = _num_or_none(preds.get('SCR_EST_3RD'))
        p4 = _num_or_none(preds.get('SCR_EST_4TH'))

        # ---------- UPDATE (예측 결과 저장) ----------
        try:
            sql_upd = """
                UPDATE USER_DATA
                SET SCR_EST_1ST = :1,
                    SCR_EST_2ND = :2,
                    SCR_EST_3RD = :3,
                    SCR_EST_4TH = :4
                WHERE USR_ID = :5
            """
            print("[DBG] UPDATE SQL:", sql_upd)
            cur.execute(sql_upd, [p1, p2, p3, p4, usr_id])  # 포지셔널 바인딩
            conn.commit()
        except cx_Oracle.DatabaseError as e:
            print("[ERR] UPDATE 실패:", e)
            return jsonify(success=False, error=f'DB UPDATE 오류: {e}'), 500

        return jsonify(success=True, predictions={'SCR_EST_1ST': p1, 'SCR_EST_2ND': p2, 'SCR_EST_3RD': p3, 'SCR_EST_4TH': p4})

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()
