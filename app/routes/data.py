# from flask import Blueprint, jsonify, request
# from services.data_service.DATA_DB import DataDB

# data_bp = Blueprint('data', __name__)

# @data_bp.route('/get/<user_id>', methods=['GET'])
# def get_data(user_id):
#     db = DataDB()
#     user_data = db.fetch_user_data(user_id)
#     return jsonify(user_data)
