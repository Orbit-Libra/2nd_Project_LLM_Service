import subprocess
import sys
import os
import json
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "."))
SERVICES_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# .env 파일 로딩
env_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f".env 파일 로딩 완료 -> {env_path}")
else:
    print(f".env 파일을 찾을 수 없습니다 -> {env_path}")

# 외부에서 실행 명령 받기
sequence_json = os.getenv("EXECUTION_SEQUENCE")
if sequence_json:
    try:
        execution_sequence = json.loads(sequence_json)
        print("외부 실행 순서 로딩 완료")
    except json.JSONDecodeError:
        print("실행 순서 JSON 파싱 실패")
        execution_sequence = []
else:
    print("외부 실행 순서 없음 -> 기본값 사용")
    # 기본: 유저 예측만 수행
    execution_sequence = [
        {"package": "Predictor", "config": "Num01_Config_XGB.json", "run": "main"} 
        # run: "main" | "user" | "both"
    ]

# 실행 루프
for step in execution_sequence:
    package = step["package"]
    config_name = step.get("config")
    run_type = step.get("run", "both")  # 기본 both

    package_path = os.path.join(PROJECT_ROOT, package)
    main_path = os.path.join(package_path, "__main__.py")

    if not os.path.isdir(package_path) or not os.path.isfile(main_path):
        print(f"실행 파일 경로 오류 -> {main_path}")
        break

    print(f"\n실행 중: {package}/__main__.py")
    if config_name:
        print(f"-> 설정 파일: {config_name}")
    print(f"-> 실행 타입(RUN_TYPE): {run_type}")

    env = os.environ.copy()
    env["PYTHONPATH"] = SERVICES_ROOT
    if config_name:
        env["MODEL_CONFIG_NAME"] = config_name
    env["RUN_TYPE"] = run_type  # ✅ Predictor에서 분기

    result = subprocess.run(
        [sys.executable, main_path],
        env=env,
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        print(f"{package} 실패 -> {result.stderr}")
        break
else:
    print("\n전체 파이프라인 완료!")