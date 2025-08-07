@echo off
REM 현재 .bat 파일 위치로 이동
cd /d "%~dp0"

REM 가상환경 활성화
call .venv\libra_env\Scripts\activate.bat

REM PYTHONPATH 설정
set PYTHONPATH=%cd%

REM 환경변수 설정
set FLASK_APP=app.main
set FLASK_ENV=development
set FLASK_DEBUG=1

REM Flask 서버를 별도 콘솔에서 실행
start cmd /k "flask run"

REM 현재 콘솔 종료
<<<<<<< HEAD
exit
=======
exit
>>>>>>> main
