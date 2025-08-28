#agent_service/api/rag_admin.py
import os
import re
import json
import glob
import hashlib
import logging
from typing import List, Dict, Any, Tuple

from flask import Blueprint, request, jsonify
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

try:
    from pypdf import PdfReader  # pypdf(신규)
except Exception:
    try:
        from PyPDF2 import PdfReader  # 구버전 호환
    except Exception:
        PdfReader = None  # 런타임에 에러 안내

rag_admin_bp = Blueprint("rag_admin", __name__)
log = logging.getLogger("rag_admin")

# ─────────────────────────────────────────────────────────────
# 환경 & 기본값
# ─────────────────────────────────────────────────────────────
DEF_PDF_DIR = os.getenv(
    "RAG_PDF_DIR",
    "services/agent_service/tools/rag_agent_tool/files/pdf",
)
DEF_CHROMA_DIR = os.getenv(
    "CHROMA_PERSIST_DIR",
    "services/agent_service/tools/rag_agent_tool/files/chroma",
)
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
)
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", os.getenv("CHUNK_SIZE", 800)))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", os.getenv("CHUNK_OVERLAP", 120)))

# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────
def _resolve_path(p: str) -> str:
    return os.path.abspath(os.path.join(os.getcwd(), p))

def _slug_ascii(s: str) -> str:
    """
    Chroma collection name 제약: 3-512 chars, [a-zA-Z0-9._-], 시작/끝은 [a-zA-Z0-9]
    한글/공백/기타 문자는 safe 치환.
    """
    # 한글 등 비ASCII → _ 로 치환
    s = re.sub(r"[^0-9A-Za-z._-]+", "_", s)
    s = s.strip("._-")
    if len(s) < 3:
        s = (s + "_xxx")[:3]
    if len(s) > 512:
        s = s[:512]
    # 시작/끝 보정
    if not re.match(r"[A-Za-z0-9]", s[:1] or ""):
        s = "x" + s
    if not re.match(r"[A-Za-z0-9]", s[-1:] or ""):
        s = s + "x"
    return s

def _file_hash(path: str) -> str:
    h = hashlib.sha1()
    h.update(path.encode("utf-8", errors="ignore"))
    return h.hexdigest()[:8]

def _split_chunks(text: str, size: int, overlap: int) -> List[str]:
    if not text:
        return []
    if size <= 0:
        return [text]
    chunks = []
    start = 0
    n = len(text)
    step = max(1, size - max(0, overlap))
    while start < n:
        end = min(n, start + size)
        chunks.append(text[start:end])
        start += step
    return chunks

# ─────────────────────────────────────────────────────────────
# EmbeddingFunction (Chroma 0.4.16+ 시그니처 대응)
# ─────────────────────────────────────────────────────────────
class SBertEmbeddingFn:
    def __init__(self, model_name: str):
        log.info("Loading embedding model: %s", model_name)
        self.model = SentenceTransformer(model_name)

    # Chroma가 이 메서드가 있으면 임베딩 함수 충돌 검증 시 사용
    def name(self) -> str:
        return f"sbert::{EMBEDDING_MODEL}"

    # Chroma 0.4.16+: __call__(self, input: List[str]) -> List[List[float]]
    def __call__(self, input: List[str]) -> List[List[float]]:
        # SentenceTransformer.encode(..., convert_to_numpy=True) -> np.ndarray
        vecs = self.model.encode(
            input,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return vecs.tolist()

# ─────────────────────────────────────────────────────────────
# Chroma client 헬퍼
# ─────────────────────────────────────────────────────────────
def _chroma() -> PersistentClient:
    os.makedirs(DEF_CHROMA_DIR, exist_ok=True)
    return PersistentClient(path=DEF_CHROMA_DIR)

def _collection_name(group_slug: str, file_path: str) -> str:
    stem = os.path.splitext(os.path.basename(file_path))[0]
    stem_slug = _slug_ascii(stem)[:64]
    return _slug_ascii(f"pdf.{group_slug}.file-{_file_hash(file_path)}.{stem_slug}")

def _extract_text_from_pdf(path: str) -> Tuple[str, List[int]]:
    """
    단순 텍스트 추출. (페이지별 문자수도 반환)
    """
    if PdfReader is None:
        raise RuntimeError("PDF 파서(PdfReader)가 로드되지 않았습니다. pypdf 또는 PyPDF2를 설치하세요.")
    reader = PdfReader(path)
    texts = []
    page_lens = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        texts.append(t)
        page_lens.append(len(t))
    return "\n\n".join(texts), page_lens

# ─────────────────────────────────────────────────────────────
# 엔드포인트: 동기화/초기화/상태
# ─────────────────────────────────────────────────────────────
@rag_admin_bp.post("/rag/reset")
def rag_reset():
    body = request.get_json(silent=True) or {}
    group = body.get("group") or "DEFAULT"
    group_slug = _slug_ascii(group)
    client = _chroma()

    # prefix로 컬렉션 정리
    # (우리가 생성하는 이름 규칙: pdf.{group_slug}.file-*)
    deleted = []
    for col in client.list_collections():
        name = getattr(col, "name", "") or ""
        if name.startswith(f"pdf.{group_slug}.file-"):
            try:
                client.delete_collection(name=name)
                deleted.append(name)
            except Exception as e:
                log.warning("Delete failed: %s (%s)", name, e)

    return jsonify({
        "ok": True,
        "reset": {"group": group, "deleted_groups": deleted}
    })

@rag_admin_bp.post("/rag/status")
def rag_status():
    body = request.get_json(silent=True) or {}
    group = body.get("group") or "DEFAULT"
    group_slug = _slug_ascii(group)
    client = _chroma()
    cols = []
    for col in client.list_collections():
        name = getattr(col, "name", "") or ""
        if name.startswith(f"pdf.{group_slug}.file-"):
            cols.append(name)
    return jsonify({"ok": True, "group": group, "collections": cols, "count": len(cols)})

@rag_admin_bp.post("/rag/sync")
def rag_sync():
    """
    요청 JSON:
      {
        "group": "서비스이용가이드",
        "base_dir": "services/agent_service/tools/rag_agent_tool/files/pdf",
        "patterns": ["*.pdf","**/*.pdf"],
        "reset": false,
        "force_rebuild": false,
        "limit": 0
      }
    """
    body = request.get_json(silent=True) or {}
    group = body.get("group") or "DEFAULT"
    group_slug = _slug_ascii(group)
    base_dir = body.get("base_dir") or DEF_PDF_DIR
    patterns = body.get("patterns") or ["*.pdf", "**/*.pdf"]
    reset = bool(body.get("reset", False))
    force_rebuild = bool(body.get("force_rebuild", False))
    limit = int(body.get("limit", 0) or 0)

    resolved = _resolve_path(base_dir)
    files: List[str] = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(resolved, pat), recursive=True))
    files = sorted(set([f for f in files if f.lower().endswith(".pdf")]))

    if limit > 0:
        files = files[:limit]

    log.info("[RAG Sync] base_dir=%s (resolved=%s) patterns=%s matched=%d",
             base_dir, resolved, patterns, len(files))
    for f in files:
        log.info("  - pdf: %s", f)

    client = _chroma()
    emb = SBertEmbeddingFn(EMBEDDING_MODEL)

    # reset=true 이면 해당 group의 컬렉션 모두 삭제
    if reset:
        for col in client.list_collections():
            name = getattr(col, "name", "") or ""
            if name.startswith(f"pdf.{group_slug}.file-"):
                try:
                    client.delete_collection(name=name)
                    log.info("Deleted collection: %s", name)
                except Exception as e:
                    log.warning("Delete failed: %s (%s)", name, e)

    indexed_files = 0
    indexed_chunks = 0
    detail: List[Dict[str, Any]] = []

    for pdf in files:
        try:
            text, page_lens = _extract_text_from_pdf(pdf)
        except Exception as e:
            log.warning("PDF read failed: %s (%s)", pdf, e)
            continue

        chunks = _split_chunks(text, CHUNK_SIZE, CHUNK_OVERLAP)
        if not chunks:
            continue

        coll_name = _collection_name(group_slug, pdf)
        # 존재 시 가져오고, 없으면 생성 (임베딩 함수 명시)
        try:
            col = client.get_collection(name=coll_name, embedding_function=emb)
        except Exception:
            col = client.get_or_create_collection(name=coll_name, embedding_function=emb)

        ids = []
        metadatas = []
        for i, c in enumerate(chunks):
            ids.append(f"{coll_name}-c{i:05d}")
            metadatas.append({
                "group": group,
                "file": os.path.basename(pdf),
                "abs_path": pdf,
                "chunk_index": i,
                "chunk_size": len(c),
            })

        # add 또는 upsert
        try:
            # add가 문서 중복 시 에러날 수 있으므로 upsert를 선호
            # (Chroma 0.4.16+ 는 upsert 지원)
            if hasattr(col, "upsert"):
                col.upsert(ids=ids, documents=chunks, metadatas=metadatas)
            else:
                # 오래된 버전 호환
                col.add(ids=ids, documents=chunks, metadatas=metadatas)

            indexed_files += 1
            indexed_chunks += len(chunks)
            detail.append({
                "file": os.path.basename(pdf),
                "abs_path": pdf,
                "collection": coll_name,
                "chunks": len(chunks)
            })
            log.info("[Upsert] %s (chunks=%d)", coll_name, len(chunks))
        except Exception as e:
            log.error("Chroma upsert failed (%s): %s", coll_name, e, exc_info=True)

    # 표준 응답: stats + 레거시 files/chunks 별칭
    return jsonify({
        "ok": True,
        "message": "sync done",
        "stats": {
            "indexed_files": indexed_files,
            "indexed_chunks": indexed_chunks
        },
        "detail": detail,
        # 레거시 호환
        "files": indexed_files,
        "chunks": indexed_chunks
    })
