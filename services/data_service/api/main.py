import sys
import os
from flask import Flask

# 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from services.data_service.api.data_api import data_api

app = Flask(__name__)
app.register_blueprint(data_api)

if __name__ == '__main__':
    app.run(port=5050, debug=True)
