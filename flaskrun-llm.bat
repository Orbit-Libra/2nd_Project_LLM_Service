@echo off
REM === [프로세스 시작 폴더 → 프로젝트 루트] ===
cd /d "%~dp0"

REM === 가상환경 활성화 ===
call .venv\libra_env\Scripts\activate.bat

REM === UTF-8 콘솔/파이썬 (한글 깨짐 방지) ===
chcp 65001 >NUL
set PYTHONUTF8=1

REM === PYTHONPATH: 프로젝트 루트 ===
set PYTHONPATH=%cd%

REM === (선택) Transformers에서 TF 로깅 억제 ===
set TRANSFORMERS_NO_TF=1

REM === Oracle Instant Client 경로를 PATH에 추가 (cx_Oracle용) ===
REM .env에 ORACLE_CLIENT_PATH를 넣어뒀다면, 필요 시 아래 줄로 PATH 보강
if defined ORACLE_CLIENT_PATH set PATH=%ORACLE_CLIENT_PATH%;%PATH%

REM === 모델 컨피그 선택 (.env에서 읽게 했다면 생략 가능) ===
REM 필요 시 직접 지정: set MODEL_CONFIG=llm_service/model/configs/gguf.json

REM === (GGUF) 하드웨어 의존적 파라미터: 배치에서 주입 ===
set LLM_THREADS=8
set LLM_CTX_SIZE=4096
set LLM_N_GPU_LAYERS=0

REM === Flask 설정 ===
set FLASK_APP=services.llm_service.api.server:create_app
set FLASK_ENV=development
set FLASK_DEBUG=0

REM === 서버 실행 ===
start cmd /k "flask run --host=0.0.0.0 --port=5150 --with-threads"
exit
