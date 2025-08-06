import os
import sys
import time
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 환경변수에서 config 파일명 가져오기
config_name = os.getenv("MODEL_CONFIG_NAME", "Num01_Config_XGB.json")
config_path = os.path.join(os.path.dirname(__file__), "..", "_Configs", config_name)

# 컨트롤러 분기 처리
if "Num01" in config_name:
    from ModelCreator.Controller_Num01 import PipelineController
elif "Num02" in config_name:
    from ModelCreator.Controller_Num02 import PipelineController
else:
    raise ValueError(f"[ERROR] 지원하지 않는 MODEL_NUM 또는 컨피그 이름: {config_name}")

def main():
    print(f"[RUNNING] ModelCreator 파이프라인 시작 -> {config_name}")
    start_time = time.time()

    controller = PipelineController(config_path=config_path)
    controller.run()

    print(f"[COMPLETE] 소요 시간: {time.time() - start_time:.2f}초")

if __name__ == "__main__":
    main()
