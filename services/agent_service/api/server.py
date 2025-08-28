import os, json, logging, inspect, re
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# RAG 관리용 블루프린트 (rag_admin.py)
from .rag_admin import rag_admin_bp

log = logging.getLogger("agent_mcp_server")
logging.basicConfig(
    level=getattr(logging, os.getenv("APP_LOG_LEVEL","INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

REGISTRY = {}  # {"rag_agent_tool.query": callable, "oracle_agent_tool.query_estimation_score": callable, ...}
CFG = {}       # 서버 전역 설정 (툴에 주입 가능)

# ─────────────────────────────────────────────────────────────
# 파라미터 추출 유틸리티
# ─────────────────────────────────────────────────────────────
def _extract_university_from_query(query: str) -> str:
    """질문에서 대학명 추출"""
    # 대학교 패턴 매칭
    patterns = [
        r'([가-힣A-Za-z]+대학교)',  # ~대학교
        r'([가-힣A-Za-z]+대)',      # ~대
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            univ = match.group(1)
            # 일반적인 지시어/한정사 제외
            if univ not in ["어느대학교", "무슨대학교", "그대학교", "해당대학교"]:
                return univ
    return ""

def _extract_year_from_query(query: str) -> int | None:
    """질문에서 연도 추출"""
    # 연도 패턴들
    patterns = [
        r'(\d{4})\s*년도?',        # 2024년도, 2024년
        r'(\d{2})\s*년도?',        # 24년도, 24년 -> 20xx로 변환
        r'(\d{4})',                # 단순 4자리 숫자
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            year_str = match.group(1)
            year = int(year_str)
            
            # 2자리 연도면 2000년대로 변환
            if year < 100:
                if year >= 20:  # 20-99 -> 2020-2099
                    year = 2000 + year
                else:  # 00-19 -> 2000-2019
                    year = 2000 + year
            
            # 합리적 범위 체크
            if 2000 <= year <= 2030:
                return year
    
    return None

# ─────────────────────────────────────────────────────────────
# 설정 로딩
# ─────────────────────────────────────────────────────────────
def _load_cfg(app_root: str):
    # 1) .env
    env_file = os.path.join(app_root, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
        log.info(".env loaded: %s", env_file)

    # 2) rag_config.json (RAG 관련)
    cfg_path = os.getenv("AGENT_CONFIG_PATH") or os.path.join(app_root, "configs", "rag_config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            rag_cfg = json.load(f)
    except Exception as e:
        log.warning("rag_config.json load fail (%s) -> defaults", e)
        rag_cfg = {
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "chunk": {"size": 800, "overlap": 120},
            "semantic_thresholds": {"web_guide": 0.46, "group_match": 0.40},
            "router": {"top_k": 5, "preferred_group": "", "seed_phrases": [], "web_guide_keywords": []}
        }

    # 3) 파일 경로 기본값
    base_files = os.path.join(app_root, "tools", "rag_agent_tool", "files")
    pdf_dir = os.getenv("RAG_PDF_DIR", os.path.join(base_files, "pdf"))
    chroma_dir = os.getenv("CHROMA_PERSIST_DIR", os.path.join(base_files, "chroma"))

    # 4) HF 캐시
    hf_home = os.getenv("HF_HOME", os.path.join(base_files, "model"))
    os.environ.setdefault("HF_HOME", hf_home)
    os.environ.setdefault("TRANSFORMERS_CACHE", hf_home)
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", hf_home)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    return {
        "RAG_PDF_DIR": pdf_dir,
        "CHROMA_PERSIST_DIR": chroma_dir,
        "EMBEDDING_MODEL": rag_cfg.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2"),
        "CHUNK_SIZE": int(rag_cfg.get("chunk", {}).get("size", 800)),
        "CHUNK_OVERLAP": int(rag_cfg.get("chunk", {}).get("overlap", 120)),
        "SEM_T_WEB_GUIDE": float(rag_cfg.get("semantic_thresholds", {}).get("web_guide", 0.46)),
        "SEM_T_GROUP": float(rag_cfg.get("semantic_thresholds", {}).get("group_match", 0.40)),
        "ROUTER": rag_cfg.get("router", {"top_k":5, "preferred_group":"", "seed_phrases":[]})
    }

# ─────────────────────────────────────────────────────────────
# 툴 등록
# ─────────────────────────────────────────────────────────────
def _invoke_register(fn, registry: dict, cfg: dict):
    try:
        sig = inspect.signature(fn)
        if len(sig.parameters) == 2:
            fn(registry, cfg)
        else:
            fn(registry)  # backward compat
    except TypeError:
        fn(registry)

def _register_builtin_tools(cfg: dict):
    # 오라클 MCP 툴
    try:
        from services.agent_service.tools.oracle_agent_tool import register_mcp_tools as reg_oracle
        _invoke_register(reg_oracle, REGISTRY, cfg)
        log.info("Oracle tools registered")
    except Exception as e:
        log.error("Failed to register Oracle tools: %s", e)

    # RAG MCP 툴
    try:
        from services.agent_service.tools.rag_agent_tool import register_mcp_tools as reg_rag
        _invoke_register(reg_rag, REGISTRY, cfg)
        log.info("RAG tools registered")
    except Exception as e:
        log.error("Failed to register RAG tools: %s", e)

# ─────────────────────────────────────────────────────────────
# MCP 호출 헬퍼
# ─────────────────────────────────────────────────────────────
def _call_tool(tool: str, args: dict):
    fn = REGISTRY.get(tool)
    if not fn:
        log.error("Tool not found: %s, available: %s", tool, list(REGISTRY.keys()))
        return {"ok": False, "error": f"unknown tool '{tool}'"}
    try:
        res = fn(args or {})
        log.info("Tool %s executed successfully, result type: %s", tool, type(res).__name__)
        if isinstance(res, dict):
            return res
        return {"ok": True, "result": res}
    except Exception as e:
        log.exception("Tool %s execution failed: %s", tool, e)
        return {"ok": False, "error": str(e)}

# 간단한 도메인 라우팅(하위호환용): query 문자열에서 툴 추론
import re as _re
_WORDS_ESTIMATION = _re.compile(r"(예측\s*점수|예측점수|cps|lps|vps)", _re.IGNORECASE)
_WORDS_RAG_GUIDE = _re.compile(r"(이용\s*가이드|가이드|마이페이지|설정|로그인|회원가입|어디(서|로)|페이지|메뉴|탭|버튼|방법)", _re.IGNORECASE)

def _guess_tool_from_payload(payload: dict) -> str | None:
    # 1) 명시된 tool 우선
    t = (payload.get("tool") or "").strip()
    if t:
        return t

    # 2) query 기반 휴리스틱
    q = (payload.get("query") or payload.get("question") or payload.get("input") or "").strip()
    log.info("Guessing tool for query: %s", q)
    
    if q:
        if _WORDS_ESTIMATION.search(q):
            log.info("Detected estimation query, routing to oracle tool")
            return "oracle_agent_tool.query_estimation_score"
        if _WORDS_RAG_GUIDE.search(q):
            log.info("Detected guide query, routing to RAG tool")
            if "rag_agent_tool.query.pageguide" in REGISTRY:
                return "rag_agent_tool.query.pageguide"
            return "rag_agent_tool.query"

    # 3) intent 기반 힌트
    intent = payload.get("intent") or {}
    kind = (intent.get("kind") or intent.get("name") or "").lower()
    reason = (intent.get("reason") or "").lower()
    if "estimation" in kind or "예측" in reason:
        return "oracle_agent_tool.query_estimation_score"
    if "usage_guide" in kind or "guide" in reason:
        if "rag_agent_tool.query.pageguide" in REGISTRY:
            return "rag_agent_tool.query.pageguide"
        return "rag_agent_tool.query"

    # 4) hints 기반 추론
    hints = payload.get("hints", [])
    if any("rag" in str(h).lower() for h in hints):
        log.info("Detected RAG hints, routing to RAG tool")
        return "rag_agent_tool.query"
    
    log.info("No specific tool pattern detected, returning None")
    return None

# ─────────────────────────────────────────────────────────────
# Flask 앱
# ─────────────────────────────────────────────────────────────
def create_app():
    app = Flask(__name__)
    app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # RAG 관리 엔드포인트 (동기화/초기화)
    app.register_blueprint(rag_admin_bp, url_prefix="/v1/tools")

    global CFG
    CFG = _load_cfg(app_root)

    _register_builtin_tools(CFG)
    log.info("=== MCP Tool Server up :5200 ===")
    log.info("- embedding_model=%s", CFG["EMBEDDING_MODEL"])
    log.info("- pdf_dir=%s", CFG["RAG_PDF_DIR"])
    log.info("- chroma_dir=%s", CFG["CHROMA_PERSIST_DIR"])
    log.info("- registered_tools=%s", ", ".join(sorted(REGISTRY.keys())))

    @app.get("/health")
    def health():
        return jsonify({
            "status":"ok",
            "embedding_model": CFG["EMBEDDING_MODEL"],
            "pdf_dir": CFG["RAG_PDF_DIR"],
            "chroma_dir": CFG["CHROMA_PERSIST_DIR"],
            "registered_tools": sorted(REGISTRY.keys()),
        })

    # ── MCP 표준 호출
    @app.post("/v1/mcp/call")
    def mcp_call():
        data = request.get_json(silent=True) or {}
        tool = (data.get("tool") or "").strip()
        args = data.get("args") or {}
        if not tool:
            return jsonify({"ok": False, "error":"tool is required"}), 400
        fn = REGISTRY.get(tool)
        if not fn:
            return jsonify({"ok": False, "error": f"unknown tool '{tool}'"}), 404
        try:
            log.info("[MCP] call tool=%s with args keys: %s", tool, list(args.keys()))
            res = fn(args)
            log.info("[MCP] tool=%s completed, result keys: %s", tool, list(res.keys()) if isinstance(res, dict) else type(res).__name__)
            return jsonify(res if isinstance(res, dict) else {"ok": True, "result": res})
        except Exception as e:
            log.exception("mcp call error: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    # ── ✔ 하위호환 브릿지: 기존 LLM이 호출하는 /v1/agent/plan_and_run
    @app.post("/v1/agent/plan_and_run")
    def compat_plan_and_run():
        """
        orchestrator.agent_client → POST /v1/agent/plan_and_run
        페이로드를 MCP 툴 호출로 매핑해 실행한다.
        """
        payload = request.get_json(silent=True) or {}
        log.info("[Compat] /v1/agent/plan_and_run called with keys: %s", list(payload.keys()))
        
        try:
            tool = _guess_tool_from_payload(payload)
            if not tool:
                log.error("Could not infer tool from payload: %s", payload)
                return jsonify({"ok": False, "error": "could not infer tool from payload"}), 400

            # 기본 args 구성
            args = payload.get("args") or {}
            
            # 질문 텍스트 확보
            query_text = ""
            if "query" not in args:
                query_text = payload.get("query") or payload.get("question") or payload.get("input") or ""
                if query_text:
                    args["query"] = query_text
            else:
                query_text = args["query"]
            
            # 기타 페이로드 정보 전달
            for k in ("usr_id","conv_id","session","slots","intent"):
                if k in payload and k not in args:
                    args[k] = payload[k]

            # 🔥 오라클 툴 전용: 파라미터 자동 추출
            if tool.startswith("oracle_agent_tool."):
                if query_text:
                    # 대학명 추출
                    if "university" not in args or not args["university"]:
                        extracted_univ = _extract_university_from_query(query_text)
                        if extracted_univ:
                            args["university"] = extracted_univ
                            log.info("[Compat] Extracted university: %s", extracted_univ)
                    
                    # 연도 추출
                    if "year" not in args or not args["year"]:
                        extracted_year = _extract_year_from_query(query_text)
                        if extracted_year:
                            args["year"] = extracted_year
                            log.info("[Compat] Extracted year: %s", extracted_year)

            log.info("[Compat] /v1/agent/plan_and_run -> %s with args: %s", tool, list(args.keys()))
            res = _call_tool(tool, args)

            log.info("[Compat] Tool result keys: %s", list(res.keys()) if isinstance(res, dict) else type(res).__name__)

            # ⬇⬇ 오케스트레이터가 바로 인식하도록 rag/final_text/final_data는 최상위로 승격
            if isinstance(res, dict):
                # RAG 결과가 있으면 최상위로 승격
                if "rag" in res:
                    out = {"ok": True, "rag": res["rag"]}
                    log.info("[Compat] RAG result promoted to top level")
                    return jsonify(out)
                # 기타 중요 키들도 승격
                elif any(key in res for key in ["final_text", "final_data", "matches"]):
                    out = {"ok": True}
                    out.update(res)
                    log.info("[Compat] Result keys promoted to top level")
                    return jsonify(out)
                # tool_result 내부에 RAG가 있는지 확인
                elif "tool_result" in res and isinstance(res["tool_result"], dict):
                    for tool_name, tool_res in res["tool_result"].items():
                        if isinstance(tool_res, dict) and "rag" in tool_res:
                            out = {"ok": True, "rag": tool_res["rag"]}
                            log.info("[Compat] RAG result found in tool_result and promoted")
                            return jsonify(out)
                # 오라클 결과 처리: result 키가 있으면 final_data로 승격
                elif tool.startswith("oracle_agent_tool.") and "result" in res:
                    if res.get("ok"):
                        out = {"ok": True, "final_data": res["result"]}
                        log.info("[Compat] Oracle result promoted to final_data")
                        return jsonify(out)

            # 기본 응답 구조
            return jsonify({"ok": True, "data": res})
        except Exception as e:
            log.exception("compat plan_and_run error: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    # ── RAG 관리 편의 엔드포인트
    @app.post("/v1/mcp/rag/sync")
    def rag_sync():
        fn = REGISTRY.get("rag_agent_tool.sync")
        if not fn:
            return jsonify({"ok": False, "error": "rag sync tool missing"}), 404
        payload = request.get_json(silent=True) or {}
        try:
            res = fn(payload)
            return jsonify(res)
        except Exception as e:
            log.exception("rag sync error: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/v1/mcp/rag/reset")
    def rag_reset():
        fn = REGISTRY.get("rag_agent_tool.reset")
        if not fn:
            return jsonify({"ok": False, "error": "rag reset tool missing"}), 404
        try:
            res = fn({})
            return jsonify(res)
        except Exception as e:
            log.exception("rag reset error: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5200, debug=os.getenv("FLASK_DEBUG","0")=="1", use_reloader=False, threaded=True)