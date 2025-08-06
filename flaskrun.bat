@echo off
REM 가상환경 활성화
call .venv\libra_env\Scripts\activate.bat

REM 프로젝트 루트로 이동
cd /d D:\workspace\project\Project_Libra\2nd_Project_LLM_Service

REM 환경변수 설정 (Flask 실행용)
set FLASK_APP=app.main
set FLASK_ENV=development

REM Flask 서버 실행
flask run