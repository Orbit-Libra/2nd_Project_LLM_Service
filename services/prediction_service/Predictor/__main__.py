import os, sys, time
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from Predictor.Controller import Controller
from Predictor.TableBuilder_User import TableBuilderUser
import json

def main():
    print("[RUNNING] Predictor 파이프라인 시작")
    start_time = time.time()

    config_name = os.getenv("MODEL_CONFIG_NAME", "Num01_Config_XGB.json")
    controller = Controller(config_name=config_name)
    controller.run()

    print(f"[COMPLETE] 소요 시간: {time.time() - start_time:.2f}초")

def userdatapredict():
    print("[RUNNING] 유저 환경점수 예측 시작")
    start_time = time.time()

    # 유저용 TableBuilder는 Num01 모델을 기반으로 하므로 해당 컨피그 로드
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "_Configs", "Num01_Config_XGB.json"
    )
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    builder = TableBuilderUser(config=config)
    builder.run()

    print(f"[COMPLETE] 유저 예측 소요 시간: {time.time() - start_time:.2f}초")

if __name__ == "__main__":
    main()
    # userdatapredict()
