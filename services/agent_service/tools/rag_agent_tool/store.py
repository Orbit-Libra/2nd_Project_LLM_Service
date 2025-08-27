# services/agent_service/tools/rag_agent_tool/store.py
import os
import json
import shutil
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple

from pypdf import PdfReader

log = logging.getLogger("rag.store")

# 우리가 관리하는 컬렉션 레지스트리 파일명
_REG = "collections.json"

# -------------------------------
# 경로/클라이언트 유틸
# -------------------------------

def ensure_dirs(pdf_dir: str, persist_dir: str):
    os.makedirs(os.path.abspath(pdf_dir), exist_ok=True)
    os.makedirs(os.path.abspath(persist_dir), exist_ok=True)

def _get_chroma_client(persist_dir: str):
    """
    Chroma 버전차를 흡수해서 항상 디스크 퍼시스트가 되도록 클라이언트를 생성한다.
    - v0.4+: PersistentClient(path=...)
    - v0.3.x: Client(Settings(chroma_db_impl='duckdb+parquet', persist_directory=...))
    """
    import chromadb
    abs_dir = os.path.abspath(persist_dir)
    os.makedirs(abs_dir, exist_ok=True)

    if hasattr(chromadb, "PersistentClient"):
        log.info("[RAG] using PersistentClient: %s", abs_dir)
        return chromadb.PersistentClient(path=abs_dir)

    from chromadb.config import Settings
    log.info("[RAG] using Client(Settings): %s", abs_dir)
    return chromadb.Client(Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory=abs_dir,
        anonymized_telemetry=False
    ))

def _persist_if_possible(cli) -> None:
    """
    일부 버전은 persist()가 필요/가능. 지원하지 않으면 조용히 스킵.
    """
    if hasattr(cli, "persist"):
        try:
            cli.persist()
            log.info("[RAG] client.persist() called")
        except Exception as e:
            log.warning("[RAG] persist() skipped: %s", e)

def _registry_path(persist_dir: str) -> str:
    return os.path.join(os.path.abspath(persist_dir), _REG)

def load_registry(persist_dir: str) -> Dict[str, Any]:
    fp = _registry_path(persist_dir)
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        log.warning("[RAG] registry load error: %s", e)
        return {}

def save_registry(persist_dir: str, reg: Dict[str, Any]) -> None:
    fp = _registry_path(persist_dir)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

# -------------------------------
# 임베딩/청크/PDF 유틸
# -------------------------------

_EMBED_CACHE = {}

def embedder(model_name: str):
    """
    SentenceTransformer 지연 로딩 + 캐시.
    (임포트 실패 시 서버 전체가 죽지 않게 여기서 임포트)
    """
    from sentence_transformers import SentenceTransformer
    if model_name not in _EMBED_CACHE:
        _EMBED_CACHE[model_name] = SentenceTransformer(model_name)
    return _EMBED_CACHE[model_name]

def _hash16(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

def file_stem(path_or_name: str) -> str:
    base = os.path.basename(path_or_name)
    return base[:-4] if base.lower().endswith(".pdf") else base

def coll_name(group: str) -> str:
    # Chroma 컬렉션 이름은 영문/숫자/구분자 권장 → 해시 사용
    return f"rag_{_hash16(group)}"

def _chunk_text(text: str, size: int, overlap: int) -> List[str]:
    """
    아주 단순한 문자기반 슬라이딩 윈도우 청크.
    (토크나이저 없이도 동작 가능하도록 설계)
    """
    t = " ".join((text or "").split())
    if not t:
        return []
    if size <= 0:
        return [t]

    out: List[str] = []
    n = len(t)
    step = max(1, size - max(0, overlap))
    i = 0
    while i < n:
        j = min(i + size, n)
        chunk = t[i:j].strip()
        if chunk:
            out.append(chunk)
        if j >= n:
            break
        i = max(0, j - overlap)
    return out

def _read_pdf_chunks(path: str, size: int, overlap: int) -> List[Tuple[int, str]]:
    """
    PDF를 페이지 단위로 텍스트 추출 후 청크로 분할한다.
    (스캔 PDF는 빈 문자열이 나올 수 있음)
    """
    reader = PdfReader(path)
    out: List[Tuple[int, str]] = []
    for pidx, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        for c in _chunk_text(txt, size, overlap):
            if c.strip():
                out.append((pidx, c))
    return out

# -------------------------------
# 인덱싱 / 초기화 / 질의
# -------------------------------

def ingest_all(
    pdf_dir: str,
    persist_dir: str,
    model_name: str,
    chunk_size: int,
    overlap: int,
    only: Optional[List[str]] = None,
    reset: bool = True
) -> Dict[str, Any]:
    """
    pdf_dir 안의 모든 PDF를 파일명 기반 그룹으로 나눠 컬렉션에 인덱싱한다.
    - only: ["서비스이용가이드"] 처럼 스템 또는 파일명을 지정하면 해당 파일만 처리
    - reset=True: 동일 그룹 컬렉션이 존재하면 드롭 후 재생성
    """
    ensure_dirs(pdf_dir, persist_dir)
    abs_pdf = os.path.abspath(pdf_dir)
    abs_persist = os.path.abspath(persist_dir)

    cli = _get_chroma_client(abs_persist)
    reg = load_registry(abs_persist)
    model = embedder(model_name)

    # 파일 목록 준비
    files: List[str] = []
    for fn in os.listdir(abs_pdf):
        if not fn.lower().endswith(".pdf"):
            continue
        if only:
            stem = file_stem(fn)
            if fn not in only and stem not in only:
                continue
        files.append(os.path.join(abs_pdf, fn))
    files.sort()

    stats: Dict[str, Any] = {"indexed_files": 0, "indexed_chunks": 0, "collections": {}}

    for path in files:
        group = file_stem(path)
        cname = coll_name(group)
        log.info("[RAG] ingest %s -> %s", os.path.basename(path), group)

        # 기존 컬렉션 리셋(요청 시)
        if reset:
            try:
                # v0.4: name으로 삭제
                cli.delete_collection(cname)
            except Exception:
                # 일부 버전은 객체 삭제 필요 → get 후 삭제 시도
                try:
                    _c = cli.get_collection(cname)
                    cli.delete_collection(_c)
                except Exception:
                    pass

        # 컬렉션 준비
        try:
            coll = cli.get_collection(cname)
        except Exception:
            coll = cli.create_collection(
                cname,
                metadata={"group": group, "source": "pdf"}
            )

        # PDF → 청크
        chunks = _read_pdf_chunks(path, chunk_size, overlap)
        if not chunks:
            log.warning("[RAG] empty pdf or no text extracted: %s", path)
            continue

        # 배치 생성
        ids, docs, metas = [], [], []
        for idx, (page, text) in enumerate(chunks):
            ids.append(f"{group}-{page}-{idx}")
            docs.append(text)
            metas.append({"group": group, "file": os.path.basename(path), "page": page})

        # 임베딩 & 업서트
        try:
            vecs = model.encode(docs, normalize_embeddings=True).tolist()
            coll.upsert(ids=ids, documents=docs, embeddings=vecs, metadatas=metas)
        except Exception as e:
            log.error("[RAG] upsert failed (%s): %s", cname, e)
            continue

        # 레지스트리 갱신
        reg[group] = {"collection": cname, "file": os.path.basename(path), "chunks": len(docs)}
        stats["indexed_files"] += 1
        stats["indexed_chunks"] += len(docs)
        stats["collections"][group] = {"name": cname, "chunks": len(docs)}

    save_registry(abs_persist, reg)
    _persist_if_possible(cli)

    # 디버그: 실제 디렉터리 나열
    try:
        log.info("[RAG] persisted at: %s", abs_persist)
        log.info("[RAG] dir listing: %s", os.listdir(abs_persist))
    except Exception:
        pass

    return stats

def list_groups(persist_dir: str) -> List[str]:
    return list(load_registry(persist_dir).keys())

def reset_all(persist_dir: str) -> Dict[str, Any]:
    """
    모든 컬렉션 삭제 + 레지스트리 제거 + 실제 파일 폴더까지 비우기(깨끗이 초기화).
    """
    abs_persist = os.path.abspath(persist_dir)
    cli = _get_chroma_client(abs_persist)
    reg = load_registry(abs_persist)

    deleted = []
    for g, info in reg.items():
        cname = info.get("collection")
        if not cname:
            continue
        try:
            cli.delete_collection(cname)
            deleted.append(g)
        except Exception:
            # 일부 버전 fallback
            try:
                _c = cli.get_collection(cname)
                cli.delete_collection(_c)
                deleted.append(g)
            except Exception:
                pass

    save_registry(abs_persist, {})

    # 실제 파일도 제거(선택)
    try:
        if os.path.isdir(abs_persist):
            for name in os.listdir(abs_persist):
                p = os.path.join(abs_persist, name)
                if os.path.isfile(p):
                    os.remove(p)
                else:
                    shutil.rmtree(p, ignore_errors=True)
            os.makedirs(abs_persist, exist_ok=True)
    except Exception:
        pass

    _persist_if_possible(cli)
    return {"deleted_groups": deleted, "persist_dir": abs_persist}

def query_group(
    persist_dir: str,
    model_name: str,
    group: str,
    query: str,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    특정 그룹(파일명 스템)에 대해 similarity top_k 검색.
    score는 (1 - cosine_distance)로 반환(클수록 유사).
    """
    abs_persist = os.path.abspath(persist_dir)
    reg = load_registry(abs_persist)
    if group not in reg:
        raise ValueError(f"unknown group: {group}")

    cname = reg[group]["collection"]
    cli = _get_chroma_client(abs_persist)
    try:
        coll = cli.get_collection(cname)
    except Exception as e:
        raise RuntimeError(f"collection not found: {cname} ({e})")

    # 쿼리 임베딩
    qv = embedder(model_name).encode([query], normalize_embeddings=True)[0].tolist()

    # 검색
    out = coll.query(
        query_embeddings=[qv],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    docs = out.get("documents", [[]])[0]
    metas = out.get("metadatas", [[]])[0]
    dists = out.get("distances", [[]])[0]  # cosine distance (작을수록 유사)

    matches = []
    for d, m, dist in zip(docs, metas, dists):
        sim = 1.0 - float(dist)
        matches.append({"text": d, "meta": m, "score": sim})

    return {"group": group, "matches": matches}
