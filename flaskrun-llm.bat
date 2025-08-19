@echo off
REM 현재 .bat 파일 위치로 이동
cd /d "%~dp0"

REM 가상환경 활성화
call .venv\libra_env\Scripts\activate.bat

REM PYTHONPATH 설정
set PYTHONPATH=%cd%

REM === Flask 앱 (팩토리 함수 사용) ===
set FLASK_APP=services.llm_service.api.server:create_app
set FLASK_ENV=development
set FLASK_DEBUG=0

REM === 캐시 디렉토리(없으면 만들어두기) - .env에도 동일 경로 선언됨 ===
if not exist "%ROOT%\services\llm_service\huggingface" mkdir "%ROOT%\services\llm_service\huggingface"

REM === LLM API 서버 실행 (0.0.0.0:5150) ===
start cmd /k "flask run --host=0.0.0.0 --port=5150 --with-threads"
exit
