# app/__init__.py
from flask import Flask, render_template
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path='../.env')

def create_app():
    app = Flask(__name__, 
                template_folder='../services/web_frontend/templates', 
                static_folder='../services/web_frontend/static')

    @app.route('/')
    def index():
        return render_template('main.html')

    return app
