# services/agent_service/tools/mcp_tool.py
import os, logging, requests
from typing import Dict, Any, Optional, List

log = logging.getLogger("agent.tools.mcp")

class MCPTool:
    """
    MCP 클라이언트 툴
    - alias: 라우터/로그에 보일 이름 (폴더명과 동일 권장: 'oracle_agent_tool', 'rag_agent_tool')
    - default_call: payload.tools 없을 때 쓸 기본 MCP 메서드 ('oracle.query_university_metric', 'rag.query' 등)
    - supports_admin_sync: RAG MCP에 /v1/mcp/rag/sync, /v1/mcp/rag/reset 위임
    """
    def __init__(self, alias: str, default_call: str, supports_admin_sync: bool = False):
        self.name = alias
        self._default_call = default_call
        self._supports_admin = supports_admin_sync

    def can_handle(self, _query: str, _hints: List[str]) -> Optional[Dict[str, Any]]:
        return {"reason":"hint matched"}

    def _endpoint_for(self, call: str) -> str:
        call = (call or "").lower()
        if call.startswith("oracle."):
            return os.getenv("MCP_ORACLE_URL") or os.getenv("MCP_BASE_URL") or "http://localhost:5300"
        if call.startswith("rag."):
            return os.getenv("MCP_RAG_URL") or os.getenv("MCP_BASE_URL") or "http://localhost:5300"
        return os.getenv("MCP_BASE_URL") or "http://localhost:5300"

    def _post(self, url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(url.rstrip("/") + path, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def run(self, _query: str, payload: Dict[str, Any], default_call_override: str | None = None) -> Dict[str, Any]:
        calls = payload.get("tools")
        if not calls:
            calls = [{"tool": (default_call_override or self._default_call), "args": (payload.get("args") or {})}]

        results = {}
        for call in calls:
            tool = (call.get("tool") or "").strip() or (default_call_override or self._default_call)
            args = call.get("args") or {}
            base = self._endpoint_for(tool)
            try:
                res = self._post(base, "/v1/mcp/call", {"tool": tool, "args": args})
            except Exception as e:
                log.exception("[%s] MCP call failed: %s (%s)", self.name, tool, e)
                results[tool] = {"ok": False, "error": str(e)}
                continue
            results[tool] = res

        return {"final_data": None, "context_snippets": [], "tool_result": results}

    def admin_sync(self, only=None, reset=True):
        if not self._supports_admin:
            return {"message": f"{self.name} does not support admin sync"}
        base = self._endpoint_for("rag.query")
        try:
            return self._post(base, "/v1/mcp/rag/sync", {"only": only, "reset": bool(reset)})
        except Exception as e:
            log.exception("[%s] MCP rag sync failed: %s", self.name, e)
            return {"status":"error","message":str(e)}

    def admin_reset(self):
        if not self._supports_admin:
            return {"message": f"{self.name} does not support admin reset"}
        base = self._endpoint_for("rag.query")
        try:
            return self._post(base, "/v1/mcp/rag/reset", {})
        except Exception as e:
            log.exception("[%s] MCP rag reset failed: %s", self.name, e)
            return {"status":"error","message":str(e)}
