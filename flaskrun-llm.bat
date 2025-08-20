@echo off
REM 현재 .bat 파일 위치로 이동
cd /d "%~dp0"

REM 가상환경 활성화
call .venv\libra_env\Scripts\activate.bat

REM PYTHONPATH 설정 (프로젝트 루트)
set PYTHONPATH=%cd%

REM (선택) TensorFlow/transformers 잡로그 억제
set TRANSFORMERS_NO_TF=1

REM llama.cpp 스레드/컨텍스트 (GGUF 모드용)
REM 물리코어에 맞춰 조정하세요.
set LLM_THREADS=8
set LLM_CTX_SIZE=4096
set LLM_N_GPU_LAYERS=0

REM Flask 설정
set FLASK_APP=services.llm_service.api.server:create_app
set FLASK_ENV=development
set FLASK_DEBUG=0

REM LLM 백엔드는 .env의 LLM_BACKEND로 제어(gguf|hf)
start cmd /k "flask run --host=0.0.0.0 --port=5150 --with-threads"
exit
