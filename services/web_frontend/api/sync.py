# services/web_frontend/api/sync.py

from flask import Blueprint, jsonify
from core_utiles.OracleDBConnection import OracleDBConnection

sync_bp = Blueprint('sync_bp', __name__)

@sync_bp.route('/api/sync-estimationfuture', methods=['POST'])
def sync_estimationfuture():
    db = OracleDBConnection()  # .env에서 LIBRA_WEB 계정 사용
    db.connect()

    try:
        db.cursor.execute("DELETE FROM ESTIMATIONFUTURE")
        db.cursor.execute("""
            INSERT INTO ESTIMATIONFUTURE
            SELECT * FROM LIBRA_DATA.ESTIMATIONFUTURE
        """)
        db.conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    finally:
        db.close()
