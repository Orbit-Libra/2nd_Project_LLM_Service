from flask import Flask, render_template, request, redirect, session, url_for
from dotenv import load_dotenv
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.user_service.login_manager import authenticate_user

load_dotenv(dotenv_path='../services/user_service/.env')

def create_app():
    app = Flask(__name__,
                template_folder='../services/web_frontend/templates',
                static_folder='../services/web_frontend/static')

    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

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

    # 학습환경 분석 페이지
    @app.route('/chart')
    def chart():
        return render_template('chart.html')

    # 발전도 분석 페이지
    @app.route('/prediction')
    def prediction():
        return render_template('page_prediction_num01.html')

    # 마이 서비스 페이지
    @app.route('/myservice')
    def my_service():
        if not session.get('user'):
            return redirect(url_for('login'))
        return render_template('page_userpage_num01.html')

    return app
