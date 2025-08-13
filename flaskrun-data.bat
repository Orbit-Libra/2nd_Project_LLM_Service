@echo off
REM 현재 .bat 파일 위치로 이동
cd /d "%~dp0"

REM 가상환경 활성화
call .venv\libra_env\Scripts\activate.bat

REM 루트 디렉토리로 이동
cd /d "%~dp0"

REM FLASK_APP 경로 설정 (데이터 서비스의 main.py 기준)
set FLASK_APP=services.data_service.api.main
set FLASK_ENV=development
set FLASK_DEBUG=1

REM Flask 서버를 별도 콘솔에서 실행
start cmd /k "flask run --host=0.0.0.0 --port=5050 --with-threads"

REM 현재 콘솔 종료
exit
