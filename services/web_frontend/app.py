from flask import Flask, render_template
import os

# 현재 파일 기준으로 web 폴더 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, '../../web')

app = Flask(
    __name__,
    template_folder=os.path.join(WEB_DIR, 'templates'),
    static_folder=os.path.join(WEB_DIR, 'static')
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/main')
def main():
    return render_template('main.html')

if __name__ == '__main__':
    app.run(debug=True)
