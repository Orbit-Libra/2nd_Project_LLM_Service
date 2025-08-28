# services/llm_service/orchestrator/agent_client.py
import os, logging, requests
from typing import Dict, Any

log = logging.getLogger("orchestrator.agent_client")

# 에이전트 서버 기본 포트: 5200
AGENT_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:5200")

def plan_and_run(payload: Dict[str, Any], timeout_sec: float | None = None) -> Dict[str, Any]:
    """
    - 환경변수로 타임아웃/재시도 제어
      AGENT_HTTP_TIMEOUT(기본 8.0초), AGENT_HTTP_RETRIES(기본 2회)
    - 네트워크 예외에 대해서는 재시도 후 최종 예외 전파
    """
    url = f"{AGENT_URL}/v1/agent/plan_and_run"
    timeout = float(os.getenv("AGENT_HTTP_TIMEOUT", "8.0")) if timeout_sec is None else float(timeout_sec)
    tries = max(1, int(os.getenv("AGENT_HTTP_RETRIES", "2")))
    last_err = None
    for i in range(tries):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_err = e
            log.warning("Agent call failed (try %d/%d): %s", i+1, tries, e)
    # 재시도 끝나면 예외 전파 (상위에서 폴백 처리)
    raise last_err if last_err else RuntimeError("Agent call failed without specific error")
