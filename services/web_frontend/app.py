from flask import Flask, request, jsonify, render_template, redirect, url_for
import os
import hashlib
from datetime import datetime
from web_frontend import web_db

# 현재 파일 기준으로 web 폴더 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, '../../web')

app = Flask(
    __name__,
    template_folder=os.path.join(WEB_DIR, 'templates'),
    static_folder=os.path.join(WEB_DIR, 'static')
)

#index에서 직접 메인으로 리다이렉트
@app.route('/')
def index():
    # return render_template('index.html')
    return redirect(url_for('main_page'))

# @app.route('/main')
# def main():
#     return render_template('main.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
