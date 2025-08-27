@echo off
cd /d "%~dp0"
call .venv\libra_env\Scripts\activate.bat
chcp 65001 >NUL
set PYTHONUTF8=1
set PYTHONPATH=%cd%

REM 루트 디렉토리로 이동
cd /d "%~dp0"

rem --- 에이전트 .env 로드 대상은 서버 코드가 처리 ---
set FLASK_APP=services.agent_service.api.server:create_app
set FLASK_ENV=development
set FLASK_DEBUG=0

start cmd /k "flask run --host=0.0.0.0 --port=5200 --with-threads"
exit
