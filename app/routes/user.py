# from flask import Blueprint, jsonify, request
# from services.user_service.USER_DB import UserDB

# user_bp = Blueprint('user', __name__)

# @user_bp.route('/info/<user_id>', methods=['GET'])
# def get_user_info(user_id):
#     db = UserDB()
#     user_info = db.get_user_profile(user_id)
#     return jsonify(user_info)
