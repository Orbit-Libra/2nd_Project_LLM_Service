import logging, numpy as np
from typing import Dict, Any, Optional, List
from sentence_transformers import SentenceTransformer

from services.agent_service.tools.base import BaseTool
from services.agent_service.tools.rag_agent_tool.tool import RagAgentTool

log = logging.getLogger("agent.tools.router")

class ToolRouter:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.tools: List[BaseTool] = [RagAgentTool(cfg)]
        self._embed = None
        r = cfg.get("ROUTER", {})
        self._keywords = r.get("web_guide_keywords", [])
        self._seed_phrases = r.get("seed_phrases", [])
        self._sem_t = float(cfg.get("SEM_T_WEB_GUIDE", 0.46))
        self._model_name = cfg["EMBEDDING_MODEL"]

    def tool_names(self): return [t.name for t in self.tools]

    def _is_web_guide_query(self, q: str) -> bool:
        return any(k in q for k in self._keywords)

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

    def select_tool(self, query: str, hints: List[str]) -> Optional[Dict[str, Any]]:
        if any(h in hints for h in ["rag_agent_tool","rag_service_guide","rag_search"]):
            for t in self.tools:
                can = t.can_handle(query, hints=["hint"])
                if can: return {"tool": t.name, **can}

        if self._is_web_guide_query(query):
            for t in self.tools:
                can = t.can_handle(query, hints=[])
                if can: return {"tool": t.name, **can}

        if self._semantic_is_webguide(query):
            for t in self.tools:
                if t.name == "rag_agent_tool":
                    return {"tool": t.name, "reason": "semantic matched"}

        return None

    def run_tool(self, plan: Dict[str, Any], query: str, payload: Dict[str, Any]):
        for t in self.tools:
            if t.name == plan["tool"]:
                return t.run(query, payload)
        raise RuntimeError(f"tool not found: {plan['tool']}")

    def sync_rag(self, only=None, reset=True):
        for t in self.tools:
            if hasattr(t, "admin_sync"):
                return t.admin_sync(only=only, reset=reset)
        return {"message":"no rag tool found"}

    def reset_rag(self):
        for t in self.tools:
            if hasattr(t, "admin_reset"):
                return t.admin_reset()
        return {"message":"no rag tool found"}
