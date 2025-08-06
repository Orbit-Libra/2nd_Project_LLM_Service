import os
import json
from core_utiles.OracleDBConnection import OracleDBConnection
from Predictor.TableBuilder_Num01 import TableBuilder as TB01
from Predictor.TableBuilder_Num02 import TableBuilder as TB02

class Controller:
    def __init__(self, config_name: str):
        # 컨피그 경로 구성
        self.config_path = os.path.join(
            os.path.dirname(__file__), "..", "_Configs", config_name
        )
        self.config = self.load_config()
        self.db = OracleDBConnection()

    def load_config(self) -> dict:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            print(f"[INFO] 컨피그 로딩 완료 -> {self.config_path}")
            return config
        except Exception as e:
            print(f"[ERROR] 컨피그 로딩 실패 -> {e}")
            raise


    def run(self):
        model_num = self.config.get("MODEL_NUM", "")
        print(f"[Controller] 예측 모델 -> {model_num}")
        
        self.db.connect()

        if model_num == "Num01":
            builder = TB01(config=self.config, conn=self.db.conn, engine=self.db.engine)
        elif model_num == "Num02":
            builder = TB02(config=self.config, conn=self.db.conn, engine=self.db.engine)
        else:
            raise ValueError(f"[ERROR] 지원되지 않는 MODEL_NUM -> {model_num}")


        builder.run()


        print("[Controller] Oracle DB 연결 종료")
        self.db.close()