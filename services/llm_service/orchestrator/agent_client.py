# services/llm_service/orchestrator/agent_client.py
import os, logging, requests
from typing import Dict, Any

log = logging.getLogger("orchestrator.agent_client")

# 에이전트 서버 기본 포트: 5200
AGENT_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:5200")

def plan_and_run(payload: Dict[str, Any], timeout_sec: float = 6.0) -> Dict[str, Any]:
    url = f"{AGENT_URL}/v1/agent/plan_and_run"
    resp = requests.post(url, json=payload, timeout=timeout_sec)
    resp.raise_for_status()
    return resp.json()
