import sys
import os
from flask import Flask

# 루트 경로 추가 (services/ 상단을 sys.path에 포함)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# 기존 데이터 API
from services.data_service.api.data_api import data_api
from services.data_service.api.num06_api import num06_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(data_api)
    app.register_blueprint(num06_bp)
    return app

app = create_app()

if __name__ == '__main__':
    app.run(port=5050, debug=True)
