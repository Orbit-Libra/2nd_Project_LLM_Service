# services/agent_service/tools/mcp_tool.py
import os, logging, requests
from typing import Dict, Any, Optional, List
from .base import BaseTool

log = logging.getLogger("agent.tools.mcp")

class MCPTool(BaseTool):
    """
    범용 MCP 클라이언트 툴
    - alias: 라우터/로그에 보일 툴 이름 (예: 'oracle_agent_tool', 'rag_agent_tool_mcp')
    - default_call: payload.tools가 비어있을 때 사용할 기본 MCP 메서드 (예: 'oracle.query_university_metric', 'rag.query')
    - supports_admin_sync: True면 admin_sync/reset을 MCP에 위임
    환경변수:
      MCP_BASE_URL (예: http://localhost:5300)  # 공용 MCP 게이트웨이
      또는 개별:
      MCP_ORACLE_URL, MCP_RAG_URL  # 각각 별 엔드포인트를 쓰고 싶다면
    """
    def __init__(self, alias: str, default_call: str, supports_admin_sync: bool = False):
        self.name = alias
        self._default_call = default_call
        self._supports_admin = supports_admin_sync

    # 라우터가 힌트로 선별하므로 여기서는 항상 True 반환해도 무방
    def can_handle(self, query: str, hints: List[str]) -> Optional[Dict[str, Any]]:
        return {"reason":"hint matched"}  # 라우터에서 이미 결정

    # MCP 게이트웨이 라우팅
    def _endpoint_for(self, call: str) -> str:
        call = call.lower()
        # 개별 베이스 URL 우선
        if call.startswith("oracle."):
            return os.getenv("MCP_ORACLE_URL") or os.getenv("MCP_BASE_URL") or "http://localhost:5300"
        if call.startswith("rag."):
            return os.getenv("MCP_RAG_URL") or os.getenv("MCP_BASE_URL") or "http://localhost:5300"
        return os.getenv("MCP_BASE_URL") or "http://localhost:5300"

    def _post(self, url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(url.rstrip("/") + path, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def run(self, query: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # payload.tools가 있으면 그대로 전달, 없으면 default_call 사용
        calls = payload.get("tools") or [{"tool": self._default_call, "args": payload.get("args", {})}]
        results = {}

        for call in calls:
            tool = (call.get("tool") or "").strip()
            args = call.get("args") or {}

            if not tool:
                tool = self._default_call

            base = self._endpoint_for(tool)

            # MCP 엔드포인트 규칙(예시):
            # - POST /v1/mcp/call  body: { "tool": "oracle.query_university_metric", "args": {...} }
            try:
                res = self._post(base, "/v1/mcp/call", {"tool": tool, "args": args})
            except Exception as e:
                log.exception("[%s] MCP call failed: %s (%s)", self.name, tool, e)
                return {"final_data": None, "tool_result": {tool: {"ok": False, "error": str(e)}}}

            results[tool] = res

        # oracle/rag 모두 공통 스키마로 래핑
        return {
            "final_data": None,
            "context_snippets": [],
            "tool_result": results
        }

    # Admin sync/reset은 rag MCP일 때만 노출(선택)
    def admin_sync(self, only=None, reset=True):
        if not self._supports_admin:
            return {"message": f"{self.name} does not support admin sync"}
        base = self._endpoint_for("rag.query")
        try:
            res = self._post(base, "/v1/mcp/rag/sync", {"only": only, "reset": bool(reset)})
            return res
        except Exception as e:
            log.exception("[%s] MCP rag sync failed: %s", self.name, e)
            return {"status":"error","message":str(e)}

    def admin_reset(self):
        if not self._supports_admin:
            return {"message": f"{self.name} does not support admin reset"}
        base = self._endpoint_for("rag.query")
        try:
            res = self._post(base, "/v1/mcp/rag/reset", {})
            return res
        except Exception as e:
            log.exception("[%s] MCP rag reset failed: %s", self.name, e)
            return {"status":"error","message":str(e)}
