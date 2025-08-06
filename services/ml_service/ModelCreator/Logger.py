import os
import json
from datetime import datetime

class PipelineLogger:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.history_file = os.path.join(log_dir, "LogHistory.json")

    def save_log(self, filename: str, full_metrics: dict, clustered_metrics: dict = None,
                    cluster_enabled: bool = False, config: dict = None, cluster_metrics: dict = None) -> dict:
        new_entry = {
            "log_num": 1,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "full": full_metrics
        }

        if cluster_enabled and clustered_metrics and config:
            cluster_utility = bool(clustered_metrics["RMSE"] < full_metrics["RMSE"])
            new_entry.update({
                "clustered": clustered_metrics,
                "cluster-utility": cluster_utility
            })

            if cluster_metrics:
                # 클러스터 ID를 문자열로 변환해서 JSON 키로 사용
                cluster_details = {str(cid): metric for cid, metric in cluster_metrics.items()}
                new_entry["cluster-details"] = cluster_details

        path = os.path.join(self.log_dir, filename)

        # 기존 로그 파일에서 history 불러오기
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                try:
                    existing = json.load(f)
                    history = existing.get("history", [])
                except json.JSONDecodeError:
                    history = []
        else:
            history = []

        # 새 로그 맨 앞에 추가
        history.insert(0, new_entry)

        # 로그 넘버링
        for i, entry in enumerate(history[:10]):
            entry["log_num"] = i + 1

        # 최대 10개 유지
        history = history[:10]

        # 저장
        log_data = {"history": history}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        print(f"[완료] 로그 저장 → {path}")
        return new_entry