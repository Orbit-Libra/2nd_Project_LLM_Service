# agent_service/api/server.py
import os, json, logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from services.agent_service.tools.router import ToolRouter

log = logging.getLogger("agent_server")
logging.basicConfig(
    level=getattr(logging, os.getenv("APP_LOG_LEVEL","INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

def _load_cfg(app_root: str):
    # 1) .env (agent_service 루트)
    env_path = os.path.join(app_root, ".")
    env_file = os.path.join(env_path, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
        log.info(".env loaded: %s", env_file)

    # 2) RAG 설정 JSON
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
            "router": {"web_guide_keywords": [], "seed_phrases": [], "preferred_group": "", "top_k": 5}
        }

    # 3) 경로 기본값(툴 내부로 고정)
    base_files = os.path.join(app_root, "tools", "rag_agent_tool", "files")
    pdf_dir = os.getenv("RAG_PDF_DIR", os.path.join(base_files, "pdf"))
    chroma_dir = os.getenv("CHROMA_PERSIST_DIR", os.path.join(base_files, "chroma"))

    # 4) HF 캐시(툴 내부)
    hf_home = os.getenv("HF_HOME", os.path.join(base_files, "model"))
    os.environ.setdefault("HF_HOME", hf_home)
    os.environ.setdefault("TRANSFORMERS_CACHE", hf_home)
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", hf_home)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    # 5) 합치기
    cfg = {
        "RAG_PDF_DIR": pdf_dir,
        "CHROMA_PERSIST_DIR": chroma_dir,
        "EMBEDDING_MODEL": rag_cfg.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2"),
        "CHUNK_SIZE": int(rag_cfg.get("chunk", {}).get("size", 800)),
        "CHUNK_OVERLAP": int(rag_cfg.get("chunk", {}).get("overlap", 120)),
        "SEM_T_WEB_GUIDE": float(rag_cfg.get("semantic_thresholds", {}).get("web_guide", 0.46)),
        "SEM_T_GROUP": float(rag_cfg.get("semantic_thresholds", {}).get("group_match", 0.40)),
        "ROUTER": rag_cfg.get("router", {})
    }
    return cfg

def create_app():
    app = Flask(__name__)
    app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    cfg = _load_cfg(app_root)

    router = ToolRouter(cfg)
    log.info("=== Agent Service up :5200 ===")
    log.info("- pdf_dir=%s", cfg["RAG_PDF_DIR"])
    log.info("- chroma_dir=%s", cfg["CHROMA_PERSIST_DIR"])
    log.info("- embedding_model=%s", cfg["EMBEDDING_MODEL"])
    log.info("- tools=%s", ", ".join(router.tool_names()))

    @app.get("/health")
    def health():
        return jsonify({
            "status":"ok",
            "pdf_dir": cfg["RAG_PDF_DIR"],
            "chroma_dir": cfg["CHROMA_PERSIST_DIR"],
            "embedding_model": cfg["EMBEDDING_MODEL"],
            "tools": router.tool_names()
        })

    # RAG 인덱스 관리(내장 RAG 사용 시만 의미 있음 / MCP-RAG일 땐 이 엔드포인트에서 MCP에 위임)
    @app.post("/v1/tools/rag/sync")
    def rag_sync():
        payload = request.get_json(silent=True) or {}
        only = payload.get("only")
        reset = bool(payload.get("reset", True))
        try:
            stats = router.sync_rag(only=only, reset=reset)
            return jsonify({"status":"ok","stats":stats})
        except Exception as e:
            log.exception("rag sync error: %s", e)
            return jsonify({"status":"error","message":str(e)}), 500

    @app.post("/v1/tools/rag/reset")
    def rag_reset():
        try:
            info = router.reset_rag()
            return jsonify({"status":"ok","reset":info})
        except Exception as e:
            log.exception("rag reset error: %s", e)
            return jsonify({"status":"error","message":str(e)}), 500

    @app.post("/v1/agent/plan_and_run")
    def plan_and_run():
        data = request.get_json(silent=True) or {}
        query = (data.get("query") or "").strip()
        hints = data.get("hints") or []
        tools_req = data.get("tools") or []
        if not query:
            return jsonify({"status":"error","message":"query is required"}), 400
        try:
            plan = router.select_tool(query=query, hints=hints, tools_req=tools_req)
            if not plan:
                return jsonify({"status":"no_tool","message":"no suitable tool"}), 200

            log.info(
                "[AGENT] tool=%s reason=%s hints=%s",
                plan["tool"], plan.get("reason",""), plan.get("matched_hints", [])
            )
            result = router.run_tool(plan, query=query, payload=data)

            # 공통 응답 스키마
            return jsonify({
                "status":"ok",
                "used":[plan["tool"]],
                "final_data": result.get("final_data"),
                "context_snippets": result.get("context_snippets", []),
                "tool_result": result.get("tool_result"),
                "debug": {"plan": plan}
            })
        except Exception as e:
            log.exception("agent plan/run error: %s", e)
            return jsonify({"status":"error","message":str(e)}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=5200,
        debug=os.getenv("FLASK_DEBUG","0")=="1",
        use_reloader=False,
        threaded=True
    )
