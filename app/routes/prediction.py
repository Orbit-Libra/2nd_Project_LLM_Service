# from flask import Blueprint, request, jsonify
# from services.prediction_service.Predictor import Controller
# from services.ml_service.ML_Loader import load_model_config
# from services.data_service.DATA_DB import DataDB
# from services.user_service.USER_DB import UserDB

# prediction_bp = Blueprint('prediction', __name__)

# @prediction_bp.route('/run', methods=['POST'])
# def run_prediction():
#     req = request.get_json()
#     user_id = req.get('user_id')
#     config_name = req.get('config_name')  # 예: "Num01_Config_XGB.json"

#     # 유저 정보 및 데이터 가져오기
#     user_db = UserDB()
#     data_db = DataDB()
#     user_info = user_db.get_user_profile(user_id)
#     user_data = data_db.fetch_user_data(user_id)

#     # 모델 로딩 및 예측 실행
#     model_config, model_pickle = load_model_config(config_name)
#     controller = Controller(config=model_config, model=model_pickle)
#     prediction_result = controller.run(user_data)

#     return jsonify({
#         "user": user_info,
#         "prediction": prediction_result
#     })
