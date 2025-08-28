# services/agent_service/tools/router.py
import logging, numpy as np
from typing import Dict, Any, Optional, List
from sentence_transformers import SentenceTransformer

from services.agent_service.tools.base import BaseTool
from services.agent_service.tools.rag_agent_tool.tool import RagAgentTool  # (내장형 RAG: fallback/옵션)
from services.agent_service.tools.mcp_tool import MCPTool  # (범용 MCP 클라이언트)

log = logging.getLogger("agent.tools.router")

RAG_HINTS = {"rag_agent_tool", "rag_service_guide", "rag_search"}
ORACLE_HINTS = {"oracle_univ_data", "oracle_agent_tool"}

class ToolRouter:
    """
    - rag_agent_tool_mcp : RAG를 MCP 서버로 위임(있으면 우선 사용)
    - rag_agent_tool     : 내장형 RAG (MCP-RAG 미사용/장애 시 fallback)
    - oracle_agent_tool  : 오라클 대학 데이터 MCP
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

        # ===== 툴 등록 =====
        self.tools: List[BaseTool] = []

        # (1) MCP-RAG (선택) — MCP 서버가 있을 때 활성화
        self.tools.append(MCPTool(
            alias="rag_agent_tool_mcp",
            default_call="rag.query",
            supports_admin_sync=True,   # /v1/tools/rag/sync 위임 가능
        ))

        # (2) Oracle MCP
        self.tools.append(MCPTool(
            alias="oracle_agent_tool",
            default_call="oracle.query_university_metric",
            supports_admin_sync=False
        ))

        # (3) 내장 RAG (fallback/옵션)
        self.tools.append(RagAgentTool(cfg))

        # ===== 라우팅 옵션 =====
        self._embed = None
        r = cfg.get("ROUTER", {})
        self._keywords = set(r.get("web_guide_keywords", []))  # 키워드 트리거(가이드/문서찾기)
        self._seed_phrases = r.get("seed_phrases", [])
        self._sem_t = float(cfg.get("SEM_T_WEB_GUIDE", 0.46))
        self._model_name = cfg["EMBEDDING_MODEL"]

    def tool_names(self) -> List[str]:
        return [t.name for t in self.tools]

    # ---------- 내부 헬퍼 ----------
    def _embedder(self):
        if self._embed is None:
            self._embed = SentenceTransformer(self._model_name)
        return self._embed

    def _semantic_is_webguide(self, q: str) -> bool:
        if not self._seed_phrases: return False
        try:
            m = self._embedder()
            qv = m.encode([q], normalize_embeddings=True)[0]
            seeds = m.encode(self._seed_phrases, normalize_embeddings=True)
            sim = float(np.max(np.dot(seeds, qv)))
            return sim >= self._sem_t
        except Exception:
            return False

    # ---------- 라우팅 ----------
    def select_tool(self, query: str, hints: List[str], tools_req: List[Dict[str, Any]] | None = None) -> Optional[Dict[str, Any]]:
        """
        1) 명시적 힌트로 우선 결정:
           - oracle_univ_data, oracle_agent_tool => oracle_agent_tool
           - rag_agent_tool, rag_service_guide, rag_search => rag_agent_tool_mcp (있으면) / 없으면 rag_agent_tool
        2) tools_req 안에 MCP 호출 명세가 들어오면 해당 alias 매칭
        3) 키워드/시맨틱으로 문서가이드성 질의면 RAG로
        """
        hints_set = set(hints or [])

        # 1-A) 오라클 우선 매칭
        if ORACLE_HINTS & hints_set:
            return {
                "tool": "oracle_agent_tool",
                "reason": "hint matched (oracle)",
                "matched_hints": list((ORACLE_HINTS & hints_set))
            }

        # 1-B) RAG 힌트 매칭 → MCP-RAG가 있으면 그쪽, 없으면 내장 RAG
        if RAG_HINTS & hints_set:
            if any(t.name == "rag_agent_tool_mcp" for t in self.tools):
                return {
                    "tool": "rag_agent_tool_mcp",
                    "reason": "hint matched (rag)",
                    "matched_hints": list((RAG_HINTS & hints_set))
                }
            return {
                "tool": "rag_agent_tool",
                "reason": "hint matched (rag: fallback to internal)",
                "matched_hints": list((RAG_HINTS & hints_set))
            }

        # 2) tools_req가 구체적으로 MCP call을 지정한 경우
        if tools_req:
            for call in tools_req:
                name = (call.get("tool") or "").lower()
                if name.startswith("oracle."):
                    return {"tool":"oracle_agent_tool", "reason":"explicit tools call (oracle)", "matched_hints":[]}
                if name.startswith("rag."):
                    if any(t.name == "rag_agent_tool_mcp" for t in self.tools):
                        return {"tool":"rag_agent_tool_mcp", "reason":"explicit tools call (rag)", "matched_hints":[]}
                    return {"tool":"rag_agent_tool", "reason":"explicit tools call (rag: fallback)", "matched_hints":[]}

        # 3) 키워드/시맨틱으로 가이드성 → RAG
        lower_q = query.lower()
        if any(k in lower_q for k in self._keywords) or self._semantic_is_webguide(query):
            if any(t.name == "rag_agent_tool_mcp" for t in self.tools):
                return {"tool":"rag_agent_tool_mcp", "reason":"semantic/keyword matched (rag)", "matched_hints":[]}
            return {"tool":"rag_agent_tool", "reason":"semantic/keyword matched (rag: fallback)", "matched_hints":[]}

        # 미매칭
        return None

    def run_tool(self, plan: Dict[str, Any], query: str, payload: Dict[str, Any]):
        for t in self.tools:
            if t.name == plan["tool"]:
                return t.run(query, payload)
        raise RuntimeError(f"tool not found: {plan['tool']}")

    # RAG 인덱스 관리: MCP-RAG가 있으면 MCP에 위임, 없으면 내장 RAG에 수행
    def sync_rag(self, only=None, reset=True):
        # 1) MCP-RAG 존재 시 → MCP에 위임
        for t in self.tools:
            if t.name == "rag_agent_tool_mcp" and hasattr(t, "admin_sync"):
                return t.admin_sync(only=only, reset=reset)
        # 2) 내장 RAG 존재 시
        for t in self.tools:
            if t.name == "rag_agent_tool" and hasattr(t, "admin_sync"):
                return t.admin_sync(only=only, reset=reset)
        return {"message":"no rag tool found"}

    def reset_rag(self):
        # 1) MCP-RAG 존재 시
        for t in self.tools:
            if t.name == "rag_agent_tool_mcp" and hasattr(t, "admin_reset"):
                return t.admin_reset()
        # 2) 내장 RAG 존재 시
        for t in self.tools:
            if t.name == "rag_agent_tool" and hasattr(t, "admin_reset"):
                return t.admin_reset()
        return {"message":"no rag tool found"}
