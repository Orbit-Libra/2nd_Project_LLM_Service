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
    캐시 디렉토리는 이 파일 기준 ../huggingface 기본값.
    """
    global _model, _pipe
    if _pipe is not None:
        return _pipe

    # --- 환경변수 읽기 (None 방지용 기본값 처리)
    HF_TOKEN    = (os.getenv("HUGGINGFACE_TOKEN") or "").strip()
    HF_MODEL_ID = (os.getenv("HF_MODEL_ID") or "MLP-KTLim/Llama-3-Korean-Bllossom-8B").strip()

    # 기본 캐시 경로: 이 파일 기준 ../huggingface
    base_dir      = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    default_cache = os.path.join(base_dir, 'huggingface')
    HF_CACHE_DIR  = (os.getenv("HF_CACHE_DIR") or default_cache)
    HF_CACHE_DIR  = str(pathlib.Path(HF_CACHE_DIR).resolve())
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
        torch_dtype=torch.bfloat16,   # fp32 → bf16 (메모리/대역폭 절감)
        low_cpu_mem_usage=True        # 로딩 피크↓
    ).eval()

    # CPU 고정(명시)
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

    # --- .env 로드: 이 파일 기준 ../.env (요청한 경로 보정 방식)
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
        JSON 예:
        {
          "message": "질문",
          "max_new_tokens": 32,
          "do_sample": false,          # 기본 False (빠름/단호)
          "temperature": 0.7,
          "top_p": 0.9,
          "repetition_penalty": 1.05,
          "no_repeat_ngram_size": 3
        }
        """
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        # 기본값: 속도 우선
        max_new_tokens      = int(data.get("max_new_tokens", 32))
        do_sample           = bool(data.get("do_sample", False))  # 기본 False = 빠른/단호한 답
        temperature         = float(data.get("temperature", 0.7))
        top_p               = float(data.get("top_p", 0.9))
        repetition_penalty  = float(data.get("repetition_penalty", 1.05))
        no_repeat_ngram_sz  = int(data.get("no_repeat_ngram_size", 3))

        pipe = _load_model()
        tok  = pipe.tokenizer

        # eos 토큰 안전 획득
        eos_id = tok.eos_token_id
        if eos_id is None:
            model_cfg = getattr(getattr(pipe, "model", None), "config", None)
            eos_id = getattr(model_cfg, "eos_token_id", None)

        # 프롬프트 최소화 (짧을수록 빠름)
        # Llama-3 chat 템플릿을 쓰고 싶다면 apply_chat_template 사용을 고려.
        prompt = message

        # 공통 생성 옵션
        gen_kwargs = dict(
            max_new_tokens=max_new_tokens,
            return_full_text=False,
        )
        if eos_id is not None:
            gen_kwargs.update(eos_token_id=eos_id, pad_token_id=eos_id)

        # 샘플링 조건부 적용(경고 방지: do_sample=False면 temperature/top_p 안 보냄)
        if do_sample:
            gen_kwargs.update(
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                no_repeat_ngram_size=no_repeat_ngram_sz,
            )
        else:
            gen_kwargs.update(do_sample=False)

        with torch.no_grad():
            out = pipe(prompt, **gen_kwargs)[0]["generated_text"]

        answer = (out or "").strip()
        return jsonify({"message": message, "answer": answer})

    return app

# 개발 편의: python server.py 로 실행 가능
if __name__ == "__main__":
    app = create_app()
    # 리로더로 이중 로드되어 OOM/지연되는 것 방지
    app.run(host="0.0.0.0", port=5150, debug=False, use_reloader=False, threaded=True)
