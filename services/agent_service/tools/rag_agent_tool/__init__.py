import os
import glob
import hashlib
import logging
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

log = logging.getLogger("rag_tool")

# ─────────────────────────────────────────────────────────────
# 환경/설정
# ─────────────────────────────────────────────────────────────
_CFG: Dict[str, Any] = {}
_MODEL = None

def _get_cfg_val(key: str, default=None):
    return _CFG.get(key, default)

def _load_model():
    global _MODEL
    if _MODEL is None:
        name = _get_cfg_val("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        log.info("[RAG] Loading embedding model: %s", name)
        _MODEL = SentenceTransformer(name)
    return _MODEL

class _SBertEmbeddingFn:
    """Chroma EmbeddingFunction 인터페이스 호환성 개선"""
    def __init__(self, model: SentenceTransformer):
        self.model = model
        self._name = f"sbert::{_get_cfg_val('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}"
    
    def name(self) -> str:
        """Chroma 호환성을 위한 name 메서드"""
        return self._name
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Chroma 0.4+ 호환 임베딩 함수"""
        if not input:
            return []
        try:
            # convert_to_numpy=False → list[list[float]] 직접 반환
            embeddings = self.model.encode(input, show_progress_bar=False, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            log.error("[RAG] Embedding generation failed: %s", e)
            # 빈 임베딩 반환 (차원수는 모델에 따라 결정)
            dim = getattr(self.model, 'get_sentence_embedding_dimension', lambda: 384)()
            return [[0.0] * dim for _ in input]

def _client() -> chromadb.Client:
    persist_dir = _get_cfg_val("CHROMA_PERSIST_DIR")
    os.makedirs(persist_dir, exist_ok=True)
    try:
        # Chroma 0.4+ 방식 시도
        log.info("[RAG] Using PersistentClient: %s", persist_dir)
        return chromadb.PersistentClient(path=persist_dir)
    except Exception as e:
        log.warning("[RAG] PersistentClient failed, trying legacy Client: %s", e)
        # 구버전 호환
        return chromadb.Client(Settings(
            is_persistent=True, 
            persist_directory=persist_dir,
            anonymized_telemetry=False
        ))

def _sanitize(s: str) -> str:
    # 3-512 chars, [a-zA-Z0-9._-], start/end alnum
    import re
    s = s.strip().lower()
    s = s.replace(" ", "-")
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = s.strip("-._")
    if not s:
        s = "default"
    return s[:128]

def _file_id(path: str) -> str:
    h = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
    return f"file-{h}"

def _iter_group_collections(group: str) -> List[str]:
    """등록된 모든 컬렉션 중 해당 그룹(prefix=pdf.<group>.)에 해당하는 이름 목록"""
    group_key = _sanitize(group or "default")
    try:
        cli = _client()
        cols = cli.list_collections() or []
        names = [c.name for c in cols if c.name.startswith(f"pdf.{group_key}.")]
        log.info("[RAG] Found %d collections for group '%s': %s", len(names), group, names[:3])
        return names
    except Exception as e:
        log.error("[RAG] Error listing collections for group '%s': %s", group, e)
        return []

# ─────────────────────────────────────────────────────────────
# 동기화/초기화(관리)
# ─────────────────────────────────────────────────────────────
def _sync_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    간단한 PDF 동기화 구현 (실제로는 rag_admin이 처리)
    """
    try:
        pdf_dir = _get_cfg_val("RAG_PDF_DIR")
        if not os.path.exists(pdf_dir):
            return {"ok": False, "error": f"PDF directory not found: {pdf_dir}"}
        
        pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
        log.info("[RAG_SYNC] Found %d PDF files in %s", len(pdf_files), pdf_dir)
        
        if not pdf_files:
            return {"ok": True, "message": "No PDF files found to sync", "files": 0, "chunks": 0}
        
        return {"ok": True, "message": f"Found {len(pdf_files)} PDF files", "files": len(pdf_files), "chunks": 0}
    except Exception as e:
        log.exception("[RAG_SYNC] Error: %s", e)
        return {"ok": False, "error": str(e)}

def _reset_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cli = _client()
        deleted = []
        for col in cli.list_collections() or []:
            if col.name.startswith("pdf."):
                try:
                    cli.delete_collection(col.name)
                    deleted.append(col.name)
                except Exception as e:
                    log.warning("[RAG_RESET] Failed to delete collection %s: %s", col.name, e)
        log.info("[RAG_RESET] Deleted %d collections", len(deleted))
        return {"ok": True, "reset": {"deleted_groups": deleted}}
    except Exception as e:
        log.exception("[RAG_RESET] Error: %s", e)
        return {"ok": False, "error": str(e)}

# ─────────────────────────────────────────────────────────────
# 질의(Query)
# ─────────────────────────────────────────────────────────────
def _query_group(args: Dict[str, Any], default_group_fallback: bool) -> str:
    # 우선순위: args.group → CFG.ROUTER.preferred_group → "default"
    group = (args.get("group") or "").strip()
    if not group:
        router = _get_cfg_val("ROUTER", {}) or {}
        group = router.get("preferred_group") or "default"

    # 존재하지 않는 그룹이면, 필요 시 default로 폴백
    if default_group_fallback:
        if not _iter_group_collections(group):
            log.info("[RAG] Group '%s' not found, falling back to 'default'", group)
            # 서비스이용가이드가 없으면 default도 확인
            if group != "default" and not _iter_group_collections("default"):
                log.warning("[RAG] Neither '%s' nor 'default' group found", group)
            return "default"
    return group

def _collect_candidates(group: str):
    try:
        cli = _client()
        model = _load_model()
        emb = _SBertEmbeddingFn(model)
        col_names = _iter_group_collections(group)
        
        if not col_names:
            log.warning("[RAG] No collection names found for group: %s", group)
            return []
        
        cols = []
        for name in col_names:
            try:
                # 임베딩 함수 없이 먼저 시도
                col = cli.get_collection(name=name)
                log.info("[RAG] Loaded collection without embedding function: %s", name)
                cols.append(col)
            except Exception as e1:
                try:
                    # 임베딩 함수와 함께 시도
                    col = cli.get_collection(name=name, embedding_function=emb)
                    log.info("[RAG] Loaded collection with embedding function: %s", name)
                    cols.append(col)
                except Exception as e2:
                    log.error("[RAG] Failed to load collection %s: %s, %s", name, e1, e2)
        return cols
    except Exception as e:
        log.error("[RAG] Error collecting candidates: %s", e)
        return []

def _merge_results(res_list: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """각 컬렉션 결과를 단일 리스트로 합쳐 score 내림차순 정렬"""
    merged: List[Dict[str, Any]] = []
    for res in res_list:
        if not isinstance(res, dict):
            continue
            
        docs = (res.get("documents") or [[]])[0] if res.get("documents") else []
        metas = (res.get("metadatas") or [[]])[0] if res.get("metadatas") else []
        dists = (res.get("distances") or [[]])[0] if res.get("distances") else []
        
        for i, txt in enumerate(docs):
            if not (txt or "").strip():
                continue
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            score = None
            if dist is not None:
                try:
                    score = 1.0 - float(dist)  # 간단 변환(가까울수록 높음)
                except Exception:
                    score = 0.5
            else:
                score = 0.5  # 기본 점수
            merged.append({"text": txt, "meta": meta, "score": score})
    
    # score(내림차순) → None은 맨 뒤
    merged.sort(key=lambda x: (-x["score"] if isinstance(x.get("score"), (int, float)) else -1))
    return merged[:top_k]

def _query_impl(args: Dict[str, Any], pageguide_mode: bool) -> Dict[str, Any]:
    q = (args.get("query") or "").strip()
    if not q:
        log.error("[RAG] Empty query received")
        return {"ok": False, "error": "query is required"}

    log.info("[RAG] Query received: '%s', pageguide_mode: %s", q, pageguide_mode)

    router = _get_cfg_val("ROUTER", {}) or {}
    top_k = int(router.get("top_k", 5))
    group = _query_group(args, default_group_fallback=True)

    log.info("[RAG] Using group: '%s', top_k: %d", group, top_k)

    cols = _collect_candidates(group)
    if not cols:
        log.warning("[RAG] No collections loaded for group '%s'", group)
        # 빈 결과라도 정상 응답으로 처리
        return {"ok": True, "rag": {"matches": []}, "message": f"No data found for group '{group}'"}

    # 각 컬렉션에 동일 질의
    results = []
    model = _load_model()
    
    for col in cols:
        try:
            # 직접 쿼리 텍스트로 검색
            r = col.query(query_texts=[q], n_results=top_k)
            results.append(r)
            doc_count = len(r.get("documents", [[]])[0]) if r.get("documents") else 0
            log.info("[RAG] Query to collection %s returned %d results", col.name, doc_count)
            
            # 결과 미리보기 (디버깅)
            if doc_count > 0:
                first_doc = r.get("documents", [[]])[0][0]
                log.info("[RAG] First result preview: %s...", first_doc[:100])
                
        except Exception as e:
            log.error("[RAG] Query failed on collection %s: %s", getattr(col, 'name', 'unknown'), e)
            # 실패해도 계속 진행

    matches = _merge_results(results, top_k)
    log.info("[RAG] Merged results: %d matches", len(matches))

    # 결과 미리보기 (디버깅)
    for i, match in enumerate(matches[:2]):
        log.info("[RAG] Match %d: score=%.3f, text=%s...", 
                i+1, match.get("score", 0), match.get("text", "")[:80])

    # 페이지가이드 모드라면, 메뉴/경로 힌트가 담긴 청크를 우선하도록 간단 가중
    if pageguide_mode and matches:
        key_tokens = ["페이지", "메뉴", "탭", "버튼", "어디", "이동", "방법", "회원", "가입", "로그인", "설정", "마이페이지"]
        def boost(m):
            s = m.get("score") or 0.0
            txt = (m.get("text") or "").lower()
            boost_found = any(t.lower() in txt for t in key_tokens)
            if boost_found:
                return s + 0.1
            return s
        
        matches.sort(key=lambda x: -boost(x))
        matches = matches[:top_k]
        log.info("[RAG] Applied pageguide boost, final matches: %d", len(matches))

    result = {"ok": True, "rag": {"matches": matches}}
    
    # 매치가 없으면 대안 메시지 제공
    if not matches:
        result["message"] = "관련 정보를 찾지 못했습니다."
    
    log.info("[RAG] Returning result with %d matches", len(matches))
    return result

# ─────────────────────────────────────────────────────────────
# MCP 레지스트리
# ─────────────────────────────────────────────────────────────
def register_mcp_tools(registry: Dict[str, Any], cfg: Dict[str, Any] | None = None):
    global _CFG
    _CFG = cfg or {}
    
    log.info("[RAG] Registering MCP tools with config keys: %s", list(_CFG.keys()))

    # 관리용
    registry["rag_agent_tool.sync"] = _sync_impl
    registry["rag_agent_tool.reset"] = _reset_impl

    # 질의용
    registry["rag_agent_tool.query"] = lambda args: _query_impl(args or {}, pageguide_mode=False)
    registry["rag_agent_tool.query.pageguide"] = lambda args: _query_impl(args or {}, pageguide_mode=True)
    
    log.info("[RAG] MCP tools registered: %s", ["rag_agent_tool.sync", "rag_agent_tool.reset", "rag_agent_tool.query", "rag_agent_tool.query.pageguide"])