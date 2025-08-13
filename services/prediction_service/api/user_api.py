from flask import Blueprint, request, jsonify, session
import requests
from .oracle_utils import get_connection

bp_user = Blueprint('bp_user', __name__, url_prefix='/api')

@bp_user.post('/user/predict_and_save')
def predict_and_save():
    if not session.get('user'):
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    data = request.get_json(silent=True) or {}
    # 예: 클라이언트에서 USR_SNM/학년별 값들 포함해 보냄
    # USR_ID는 세션으로 식별
    try:
        # 1) 예측 서비스 호출
        url = 'http://localhost:5100/predict/user'
        res = requests.post(url, json=data, timeout=10)
        if not res.ok:
            return jsonify(success=False, error=f'예측 서비스 오류: {res.text}'), 502
        body = res.json()
        if not body.get('success'):
            return jsonify(success=False, error=body.get('error','예측 실패')), 502

        preds = body.get('predictions', {})

        # 2) USER_DATA 업데이트
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE USER_DATA
                SET SCR_EST_1ST = :p1,
                    SCR_EST_2ND = :p2,
                    SCR_EST_3RD = :p3,
                    SCR_EST_4TH = :p4
                WHERE USR_ID = :uid
            """, p1=preds.get('SCR_EST_1ST'),
                 p2=preds.get('SCR_EST_2ND'),
                 p3=preds.get('SCR_EST_3RD'),
                 p4=preds.get('SCR_EST_4TH'),
                 uid=session['user'])
            conn.commit()
        finally:
            cur.close()
            conn.close()

        return jsonify(success=True, predictions=preds)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
