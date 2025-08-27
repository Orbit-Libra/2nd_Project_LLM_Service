import logging, numpy as np
from typing import Dict, Any, Optional, List
from sentence_transformers import SentenceTransformer

from services.agent_service.tools.base import BaseTool
from services.agent_service.tools.rag_agent_tool.store import (
    ingest_all, reset_all, load_registry, query_group, embedder
)

log = logging.getLogger("rag.tool")

class RagAgentTool(BaseTool):
    name = "rag_agent_tool"

    def __init__(self, cfg: Dict[str, Any]):
        super().__init__(cfg)
        r = cfg.get("ROUTER", {})
        self._preferred_group = r.get("preferred_group") or ""
        self._top_k_default = int(r.get("top_k", 5))
        self._group_t = float(cfg.get("SEM_T_GROUP", 0.40))
        self._model_name = cfg["EMBEDDING_MODEL"]

    def can_handle(self, query: str, hints: List[str]) -> Optional[Dict[str, Any]]:
        if any(h in hints for h in ["hint","rag_agent_tool","rag_service_guide","rag_search"]):
            return {"reason":"hint matched"}
        KW = [
          "이용","가이드","어디","이동","메뉴","버튼","페이지",
          "로그인","회원가입","비밀번호","개인정보","예측점수","마이페이지","설정"
        ]
        if any(k in query for k in KW):
            return {"reason":"keyword matched"}
        return None

    def _choose_group(self, query: str) -> Optional[str]:
        reg = load_registry(self.cfg["CHROMA_PERSIST_DIR"])
        groups = list(reg.keys())
        if not groups: return None
        if len(groups) == 1: return groups[0]
        for g in groups:
            if g in query: return g

        model: SentenceTransformer = embedder(self._model_name)
        qv = model.encode([query], normalize_embeddings=True)[0]
        gvecs = model.encode(groups, normalize_embeddings=True)
        sims = np.dot(gvecs, qv)
        idx = int(np.argmax(sims)); best, score = groups[idx], float(sims[idx])
        log.info("[RAG] group semantic match: %s (%.3f)", best, score)
        if score >= self._group_t:
            return best
        return self._preferred_group or groups[0]

    def run(self, query: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        group = self._choose_group(query)
        if not group:
            return {"final_data":{"notice":"등록된 PDF가 없습니다."},"context_snippets":[]}

        top_k = int(payload.get("top_k") or self._top_k_default)
        res = query_group(
            persist_dir=self.cfg["CHROMA_PERSIST_DIR"],
            model_name=self._model_name,
            group=group, query=query, top_k=top_k
        )
        snippets = [{
            "text": m["text"],
            "source": f"{m['meta'].get('file','?')}#p{m['meta'].get('page','?')}",
            "score": m["score"]
        } for m in res["matches"]]
        return {
            "final_data": {"group": group, "summary_hint": "서비스 이용 관련 근거 스니펫입니다. 버튼/메뉴/경로를 중심으로 간결히 답하세요."},
            "context_snippets": snippets
        }

    # 관리자용
    def admin_sync(self, **kwargs) -> Dict[str, Any]:
        from services.agent_service.tools.rag_agent_tool.store import ingest_all
        only = kwargs.get("only"); reset = bool(kwargs.get("reset", True))
        return ingest_all(
            pdf_dir=self.cfg["RAG_PDF_DIR"],
            persist_dir=self.cfg["CHROMA_PERSIST_DIR"],
            model_name=self._model_name,
            chunk_size=int(self.cfg["CHUNK_SIZE"]),
            overlap=int(self.cfg["CHUNK_OVERLAP"]),
            only=only, reset=reset
        )

    def admin_reset(self) -> Dict[str, Any]:
        return reset_all(self.cfg["CHROMA_PERSIST_DIR"])
