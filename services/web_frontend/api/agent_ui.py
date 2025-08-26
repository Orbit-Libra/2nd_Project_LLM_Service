# services/web_frontend/api/agent_ui.py
import os
from flask import Blueprint, render_template, session

agent_ui = Blueprint("agent_ui", __name__, url_prefix="/agent")

@agent_ui.route("/", methods=["GET"])
def agent_page():
    usr_name = session.get("user_name", "")
    usr_snm  = session.get("user_univ", "")
    return render_template("agent_service.html", usr_name=usr_name, usr_snm=usr_snm)
