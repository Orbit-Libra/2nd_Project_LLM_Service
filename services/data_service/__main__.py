import subprocess
import sys
import os
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "."))
CONFIGS_DIR = os.path.join(PROJECT_ROOT, "_Configs")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# .env 파일 로딩
env_path = os.path.join(CONFIGS_DIR, ".env")
if not os.path.exists(env_path):
    print(f".env 파일을 찾을 수 없습니다 ➜ {env_path}")
else:
    load_dotenv(env_path)
    print(f".env 파일 로딩 완료 → {env_path}")

# 실행 순서 정의
execution_sequence = [
    {"package": "DataHandling"},
    {"package": "DBHandling"}
]

for step in execution_sequence:
    package = step["package"]
    config_name = step.get("config")

    package_path = os.path.join(PROJECT_ROOT, package)
    main_path = os.path.join(package_path, "__main__.py")

    if not os.path.isdir(package_path) or not os.path.isfile(main_path):
        print(f"실행 파일 경로 오류 -> {main_path}")
        break

    print(f"\n실행 중: {package}/__main__.py")
    if config_name:
        print(f"-> 설정 파일: {config_name}")

    env = os.environ.copy()
    env["PYTHONPATH"] = PROJECT_ROOT
    if config_name:
        env["MODEL_CONFIG_NAME"] = config_name

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
