import os
import pathlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# transformers
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch

_model = None
_pipe = None

def _ensure_dir(p: str):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def _load_model():
    """
    환경변수 기반으로 HF 모델을 1회 로딩.
    캐시 디렉토리는 services/llm_service/huggingface 기본값.
    """
    global _model, _pipe
    if _pipe is not None:
        return _pipe

    # --- 환경변수 읽기
    HF_TOKEN     = (os.getenv("HUGGINGFACE_TOKEN")).strip()
    HF_MODEL_ID  = (os.getenv("HF_MODEL_ID")).strip()

    # 기본 캐시 경로: 이 파일 기준 ../huggingface
    base_dir     = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    default_cache= os.path.join(base_dir, 'huggingface')
    HF_CACHE_DIR = (os.getenv("HF_CACHE_DIR") or default_cache)
    HF_CACHE_DIR = str(pathlib.Path(HF_CACHE_DIR).resolve())
    _ensure_dir(HF_CACHE_DIR)

    # (옵션) CPU 스레드 튜닝 - 환경변수로 제어
    # 예: LLM_TORCH_THREADS=8, LLM_OMP_THREADS=4, LLM_MKL_THREADS=4
    try:
        torch_threads = int(os.getenv("LLM_TORCH_THREADS", "0"))
    except ValueError:
        torch_threads = 0
    if torch_threads > 0:
        torch.set_num_threads(torch_threads)
        torch.set_num_interop_threads(1)
    os.environ.setdefault("OMP_NUM_THREADS", os.getenv("LLM_OMP_THREADS", "4"))
    os.environ.setdefault("MKL_NUM_THREADS", os.getenv("LLM_MKL_THREADS", "4"))

    # 로깅(민감정보 제외)
    print(f"[LLM] Loading model: {HF_MODEL_ID}")
    print(f"[LLM] Cache dir    : {HF_CACHE_DIR}")

    # --- 토크나이저/모델 로드 (bf16 + 저메모리)
    tokenizer = AutoTokenizer.from_pretrained(
        HF_MODEL_ID,
        token=HF_TOKEN or None,
        cache_dir=HF_CACHE_DIR,
        trust_remote_code=True,
        use_fast=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        HF_MODEL_ID,
        token=HF_TOKEN or None,
        cache_dir=HF_CACHE_DIR,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,   # ★ fp32 → bf16
        low_cpu_mem_usage=True        # ★ 로딩 피크↓
    ).eval()

    # CPU 고정(자동도 되지만 명시)
    _pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device_map={"": "cpu"},
        torch_dtype=torch.bfloat16
    )
    return _pipe

def create_app():
    app = Flask(__name__)

    # --- .env 로드: 이 파일 기준 ../.env  (요청하신 경로 보정 방식)
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)

    # 기동 시 1회 로딩
    _ = _load_model()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/generate")
    def generate():
        """
        JSON: { "message": "질문", "max_new_tokens": 32, "temperature": 0.0, "top_p": 1.0 }
        """
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        # 속도 최우선 기본값
        max_new_tokens = int(data.get("max_new_tokens", 32))   # ★ 32 ~ 64 권장
        temperature    = float(data.get("temperature", 0.0))   # ★ 탐욕적 디코딩
        top_p          = float(data.get("top_p", 1.0))

        pipe = _load_model()
        tok = pipe.tokenizer
        eos_id = tok.eos_token_id or getattr(getattr(pipe, "model", None), "config", None) and pipe.model.config.eos_token_id

        # 프롬프트 최소화 (짧을수록 빠름)
        prompt = message

        with torch.no_grad():
            out = pipe(
                prompt,
                max_new_tokens=max_new_tokens,
                do_sample=False,                 # ★ 샘플링 OFF → 빠르고 안정
                temperature=temperature,         # do_sample=False면 무시되지만 인터페이스 유지
                top_p=top_p,                     # 동일
                eos_token_id=eos_id,             # ★ 종료 강제
                pad_token_id=eos_id,             # 경고 방지
                return_full_text=False           # ★ 답변만 반환
            )[0]["generated_text"]

        answer = (out or "").strip()
        return jsonify({"message": message, "answer": answer})

    return app

# 개발 편의: python server.py 로 실행 가능
if __name__ == "__main__":
    app = create_app()
    # 리로더로 이중 로드되어 OOM/지연되는 것 방지
    app.run(host="0.0.0.0", port=5150, debug=False, use_reloader=False, threaded=True)
