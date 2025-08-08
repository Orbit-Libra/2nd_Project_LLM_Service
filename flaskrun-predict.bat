@echo off
REM ==============================
REM Prediction Service Flask API 자동 실행
REM ==============================

REM 현재 .bat 파일 위치로 이동
cd /d "%~dp0"

REM 가상환경 활성화
call .venv\libra_env\Scripts\activate.bat

REM 루트 디렉토리로 이동
cd /d "%~dp0"

REM FLASK_APP 경로 설정 (prediction_service의 API server.py 기준)
set FLASK_APP=services.prediction_service.api.server
set FLASK_ENV=development
set FLASK_DEBUG=1

REM Prediction API 서버 실행 (포트: 5100)
start cmd /k "flask run --port=5100"

REM 현재 콘솔 종료
exit
