#services/web_frontend/api/qna_routes.py
from flask import Blueprint

# 블루프린트 생성
qna_bp = Blueprint('qna', __name__, url_prefix='/qna')

# 아래 import들은 qna_bp가 만들어진 뒤여야 함.
# 이 import로 각 파일의 라우트들이 qna_routes에 등록됨.
from . import qna_list    # noqa: F401
from . import qna_write   # noqa: F401
from . import qna_detail  # noqa: F401
