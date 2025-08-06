# app/__init__.py
from flask import Flask, render_template
from dotenv import load_dotenv
import os

# 환경변수 로딩
load_dotenv(dotenv_path='../.env')

# Blueprint 모듈 import
# from app.routes.data import data_bp
# from app.routes.ml import ml_bp
# from app.routes.prediction import prediction_bp
# from app.routes.user import user_bp
# from app.routes.llm import llm_bp

def create_app():
    # __file__ 기준으로 services/web_frontend 경로 계산
    app = Flask(__name__,
                template_folder='../services/web_frontend/templates',
                static_folder='../services/web_frontend/static')

    # 기본 페이지 라우트
    @app.route('/')
    def index():
        return render_template('index.html')

    # # Blueprint 등록
    # app.register_blueprint(data_bp, url_prefix='/data')
    # app.register_blueprint(ml_bp, url_prefix='/ml')
    # app.register_blueprint(prediction_bp, url_prefix='/predict')
    # app.register_blueprint(user_bp, url_prefix='/user')
    # app.register_blueprint(llm_bp, url_prefix='/chat')

    return app
