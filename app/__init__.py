import os
import sys
import logging
from flask import Flask, render_template, request, redirect, session, url_for
from dotenv import load_dotenv

# --- 로깅 기본 설정 (환경변수로 레벨 조절 가능) ---
LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s - %(message)s"
)
app_log = logging.getLogger("webapp")
werk_log = logging.getLogger("werkzeug")  # 접속 로그
werk_log.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# 경로 설정
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)

# 사용자 인증 모듈
from services.user_service.login_manager import authenticate_user
from services.web_frontend.api.sync import sync_bp
from services.web_frontend.api.chart_data import chart_data_bp
from services.web_frontend.api.profile_api import bp_profile
from services.web_frontend.api.register_api import bp_register
from services.web_frontend.api.user_api import bp_user
from services.web_frontend.api.admin_system import admin_system_bp
from services.web_frontend.api.chatbot_api import chatbot_bp
from services.web_frontend.api.agent_ui import agent_bp
from services.web_frontend.api.rag_api import rag_bp
from services.user_service.predict_sync import bp_predict_sync
from services.user_service.user_analysis import bp_user_analysis


# Oracle 연결을 위한 import (profile 라우트에서 사용)
try:
    from services.web_frontend.api.oracle_utils import get_connection
except ImportError:
    print("Warning: oracle_utils 모듈을 찾을 수 없습니다.")
    def get_connection():
        raise Exception("Oracle 연결이 설정되지 않았습니다.")

# 환경 변수 로드 (유저 서비스 .env 우선)
load_dotenv(dotenv_path=os.path.join(BASE_DIR, 'services/user_service/.env'))

def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, 'services/web_frontend/templates'),
        static_folder=os.path.join(BASE_DIR, 'services/web_frontend/static')
    )

    # 세션 키
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

    # Blueprint 등록
    app.register_blueprint(sync_bp)
    app.register_blueprint(chart_data_bp)
    app.register_blueprint(bp_register)
    app.register_blueprint(bp_profile)
    app.register_blueprint(bp_user)
    app.register_blueprint(bp_predict_sync)
    app.register_blueprint(bp_user_analysis)
    app.register_blueprint(admin_system_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(rag_bp)

    # 메인 페이지
    @app.route('/')
    def index():
        return render_template('main.html')

    # 로그인
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            usr_id = request.form['usr_id']
            usr_pw = request.form['usr_pw']

            if authenticate_user(usr_id, usr_pw):
                session['user'] = usr_id
                session['is_admin'] = (usr_id == 'libra_admin')
                return redirect(url_for('index'))
            else:
                error = '아이디 또는 비밀번호가 올바르지 않습니다.'
        return render_template('login.html', error=error)

    # 회원가입 페이지 (템플릿 라우트)
    @app.route('/register', methods=['GET'], endpoint='register')
    def register_page():
        return render_template('register.html')

    # 로그아웃
    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('index'))

    # 관리자 페이지
    @app.route('/admin')
    def admin_page():
        if session.get('user') != 'libra_admin':
            return redirect(url_for('login'))
        return render_template('admin.html')

    # 학습환경 분석 페이지 (차트 페이지 1 - 단일 연도 분석)
    @app.route('/chart')
    def chart():
        return render_template('chartpage1.html')

    # 발전도 분석 페이지 (차트 페이지 2 - 다중 연도 예측 분석)
    @app.route('/prediction')
    def prediction():
        return render_template('chartpage2.html')

    # 기존 예측 페이지 (legacy - 호환성을 위해 유지)
    @app.route('/prediction_old')
    def prediction_old():
        return render_template('page_prediction_num01.html')

    # 마이 서비스 페이지
    @app.route('/myservice')
    def my_service():
        if not session.get('user'):
            return redirect(url_for('login'))

        # DB에서 현재 로그인 사용자 기본정보 조회
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT USR_NAME, USR_SNM FROM USER_DATA WHERE USR_ID = :1", [session['user']])
            row = cur.fetchone()
            cur.close(); conn.close()

            usr_name = row[0] if row else ''
            usr_snm  = row[1] if row else ''
        except Exception as e:
            print(f"[ERR] myservice DB 조회 실패: {e}")
            usr_name = ''
            usr_snm = ''

        return render_template('userservice.html', usr_name=usr_name, usr_snm=usr_snm)
    
    @app.route('/profile')
    def profile():
        if not session.get('user'):
            return redirect(url_for('login'))

        conn = None
        cur = None
        user_row = {}
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT USR_ID, USR_NAME, USR_EMAIL, USR_SNM,
                       "1ST_YR","1ST_USR_CPS","1ST_USR_LPS","1ST_USR_VPS",
                       "2ND_YR","2ND_USR_CPS","2ND_USR_LPS","2ND_USR_VPS",
                       "3RD_YR","3RD_USR_CPS","3RD_USR_LPS","3RD_USR_VPS",
                       "4TH_YR","4TH_USR_CPS","4TH_USR_LPS","4TH_USR_VPS"
                FROM USER_DATA
                WHERE USR_ID = :1
            """, [session['user']])
            r = cur.fetchone()
            if r:
                user_row = {
                  'usr_id': r[0], 'usr_name': r[1], 'usr_email': r[2], 'usr_snm': r[3],
                  'y1': r[4],  'cps1': r[5],  'lps1': r[6],  'vps1': r[7],
                  'y2': r[8],  'cps2': r[9],  'lps2': r[10], 'vps2': r[11],
                  'y3': r[12], 'cps3': r[13], 'lps3': r[14], 'vps3': r[15],
                  'y4': r[16], 'cps4': r[17], 'lps4': r[18], 'vps4': r[19],
                }
        except Exception as e:
            print("[ERR]/profile fetch:", e)
        finally:
            if cur: cur.close()
            if conn: conn.close()

        return render_template('profile.html', user=user_row)

    # 임시 회원정보 수정 페이지(나중에 구현)
    @app.route('/profile/edit')
    def edit_profile():
        if not session.get('user'):
            return redirect(url_for('login'))
        return "<h3>회원정보 수정 페이지는 준비 중입니다.</h3>"

    # 차트 데이터 API 테스트 페이지 (개발/디버깅용)
    @app.route('/chart-test')
    def chart_test():
        if session.get('user') != 'libra_admin':
            return redirect(url_for('login'))
        return render_template('chart_test.html')

    return app


# 개발용 실행
if __name__ == '__main__':
    app = create_app()
    # 배포 시에는 아래 옵션 조정(예: debug=False, host='0.0.0.0')
    app.run(debug=True)