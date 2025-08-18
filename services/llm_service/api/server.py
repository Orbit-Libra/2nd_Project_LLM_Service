import os
import pathlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# transformers 로딩
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

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

    HF_TOKEN      = os.getenv("HUGGINGFACE_TOKEN", "").strip()
    HF_MODEL_ID   = os.getenv("HF_MODEL_ID", "MLP-KTLim/Llama-3-Korean-Bllossom-8B").strip()
    HF_CACHE_DIR  = os.getenv("HF_CACHE_DIR", os.path.join(os.getcwd(), "..", "huggingface"))

    # 절대경로 보정
    HF_CACHE_DIR = str(pathlib.Path(HF_CACHE_DIR).resolve())
    _ensure_dir(HF_CACHE_DIR)

    # 토큰/모델 로깅(민감정보는 출력하지 않음)
    print(f"[LLM] Loading model: {HF_MODEL_ID}")
    print(f"[LLM] Cache dir    : {HF_CACHE_DIR}")

    # 토크나이저/모델 로드
    tokenizer = AutoTokenizer.from_pretrained(
        HF_MODEL_ID,
        token=HF_TOKEN if HF_TOKEN else None,
        cache_dir=HF_CACHE_DIR,
        trust_remote_code=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        HF_MODEL_ID,
        token=HF_TOKEN if HF_TOKEN else None,
        cache_dir=HF_CACHE_DIR,
        trust_remote_code=True
    )

    # 파이프라인 (지연 상관없으면 text-generation 사용)
    _pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device_map="auto",             # GPU 있으면 자동 할당, 없으면 CPU
        torch_dtype="auto"
    )
    return _pipe

def create_app():
    app = Flask(__name__)

    # .env 로드 (services/llm_service/.env)
    root = pathlib.Path(__file__).resolve().parents[2]  # 프로젝트 루트
    llm_root = root / "services" / "llm_service"
    env_path = llm_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    # 서버 기동 시 1회 로딩 (선로드)
    _ = _load_model()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/generate")
    def generate():
        """
        JSON: { "message": "질문", "max_new_tokens": 512, "temperature": 0.7, "top_p": 0.9 }
        """
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        max_new_tokens = int(data.get("max_new_tokens", 512))
        temperature    = float(data.get("temperature", 0.7))
        top_p          = float(data.get("top_p", 0.9))

        pipe = _load_model()

        prompt = f"""[SYSTEM] 당신은 한국어 질문에 간결하고 정확히 답하는 비서입니다.
[USER] {message}
[ASSISTANT]"""

        out = pipe(
            prompt,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            pad_token_id=pipe.tokenizer.eos_token_id if pipe.tokenizer.eos_token_id else None
        )[0]["generated_text"]

        # 생성된 전체 텍스트에서 어시스턴트 부분만 최대한 깔끔히 추출
        answer = out.split("[ASSISTANT]")[-1].strip()

        return jsonify({
            "message": message,
            "answer": answer
        })

    return app

# 개발 편의: python server.py 로도 실행 가능
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5150, debug=True, threaded=True)
