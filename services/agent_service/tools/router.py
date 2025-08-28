# services/agent_service/tools/router.py
import logging, numpy as np
from typing import Dict, Any, Optional, List
from sentence_transformers import SentenceTransformer

from .mcp_tool import MCPTool

log = logging.getLogger("agent.tools.router")

RAG_HINTS = {"rag_agent_tool", "rag_service_guide", "rag_search"}
ORACLE_HINTS = {"oracle_univ_data", "oracle_agent_tool"}

GUIDE_KWS = {
    "서비스이용가이드","서비스 이용 가이드","이용가이드","이용 가이드",
    "개인정보","비밀번호","로그인","회원가입","탈퇴","인증",
    "마이페이지","프로필","계정","설정",
    "어디로 이동","어디에서","어디에","어떻게 가","어떻게 들어가",
    "메뉴","탭","버튼","페이지","절차","방법","가이드","도움말","고객센터"
}
PREDICT_KWS = {"예측점수","예측","prediction","estimate","estimation"}

class ToolRouter:
    """
    툴:
      - rag_agent_tool (MCP): rag.query / rag.query.pageguide (분기)
      - oracle_agent_tool (MCP): oracle.query_university_metric / oracle.query_estimation_score (분기)
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.tools: List[MCPTool] = [
            MCPTool(alias="rag_agent_tool",     default_call="rag.query", supports_admin_sync=True),
            MCPTool(alias="oracle_agent_tool",  default_call="oracle.query_university_metric", supports_admin_sync=False),
        ]
        self._embed = None
        r = cfg.get("ROUTER", {})
        self._seed_phrases = r.get("seed_phrases", [])
        self._sem_t = float(cfg.get("SEM_T_WEB_GUIDE", 0.46))
        self._model_name = cfg["EMBEDDING_MODEL"]

    def tool_names(self) -> List[str]:
        return [t.name for t in self.tools]

    def _embedder(self):
        if self._embed is None:
            self._embed = SentenceTransformer(self._model_name)
        return self._embed

    def _semantic_is_webguide(self, q: str) -> bool:
        if not self._seed_phrases:
            return False
        try:
            m = self._embedder()
            qv = m.encode([q], normalize_embeddings=True)[0]
            seeds = m.encode(self._seed_phrases, normalize_embeddings=True)
            sim = float(np.max(np.dot(seeds, qv)))
            return sim >= self._sem_t
        except Exception:
            return False

    def _has_any(self, q: str, kws: set[str]) -> bool:
        return any(k in q for k in kws)

    def select_tool(self, query: str, hints: List[str], tools_req: List[Dict[str, Any]] | None = None) -> Optional[Dict[str, Any]]:
        hints_set = set(hints or [])
        lower_q = query.lower()

        # 1) 명시 힌트 — 오라클
        if ORACLE_HINTS & hints_set:
            default_call = "oracle.query_university_metric"
            if self._has_any(query, PREDICT_KWS) or ("prediction" in hints_set):
                default_call = "oracle.query_estimation_score"
            return {
                "tool": "oracle_agent_tool",
                "reason": "hint matched (oracle)",
                "matched_hints": list(ORACLE_HINTS & hints_set),
                "default_call_override": default_call,
            }

        # 2) 명시 힌트 — RAG
        if RAG_HINTS & hints_set:
            default_call = "rag.query"
            # page guide 추정: 가이드/네비 류 힌트 포함 시
            if ("rag_service_guide" in hints_set) or self._has_any(query, GUIDE_KWS) or self._semantic_is_webguide(query):
                default_call = "rag.query.pageguide"
            return {
                "tool": "rag_agent_tool",
                "reason": "hint matched (rag)",
                "matched_hints": list(RAG_HINTS & hints_set),
                "default_call_override": default_call,
            }

        # 3) tools_req에 MCP 호출이 온 경우 명시 분기
        if tools_req:
            for call in tools_req:
                name = (call.get("tool") or "").lower()
                if name.startswith("oracle."):
                    return {
                        "tool":"oracle_agent_tool",
                        "reason":"explicit tools call (oracle)",
                        "matched_hints":[],
                        "default_call_override": name
                    }
                if name.startswith("rag."):
                    return {
                        "tool":"rag_agent_tool",
                        "reason":"explicit tools call (rag)",
                        "matched_hints":[],
                        "default_call_override": name
                    }

        # 4) 키워드/시맨틱: 가이드 추정 → RAG.pageguide
        if self._has_any(query, GUIDE_KWS) or self._semantic_is_webguide(query):
            return {
                "tool":"rag_agent_tool",
                "reason":"semantic/keyword matched (rag)",
                "matched_hints":[],
                "default_call_override":"rag.query.pageguide"
            }

        # 5) 예측점수 키워드 → 오라클(예측)
        if self._has_any(query, PREDICT_KWS):
            return {
                "tool":"oracle_agent_tool",
                "reason":"keyword matched (oracle prediction)",
                "matched_hints":[],
                "default_call_override":"oracle.query_estimation_score"
            }

        return None

    def run_tool(self, plan: Dict[str, Any], query: str, payload: Dict[str, Any]):
        for t in self.tools:
            if t.name == plan["tool"]:
                return t.run(query, payload, default_call_override=plan.get("default_call_override"))
        raise RuntimeError(f"tool not found: {plan['tool']}")

    # MCP-RAG 관리 위임
    def sync_rag(self, only=None, reset=True):
        for t in self.tools:
            if t.name == "rag_agent_tool" and hasattr(t, "admin_sync"):
                return t.admin_sync(only=only, reset=reset)
        return {"message":"no rag tool found"}

    def reset_rag(self):
        for t in self.tools:
            if t.name == "rag_agent_tool" and hasattr(t, "admin_reset"):
                return t.admin_reset()
        return {"message":"no rag tool found"}
