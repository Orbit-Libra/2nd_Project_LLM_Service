import os
import pathlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# 전역 핸들: 백엔드 어댑터 인스턴스
_GEN = None


def _ensure_dir(p: str):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)


# ========== SYSTEM PROMPT 로더 ==========
def _read_system_prompt() -> str:
    """
    SYSTEM_PROMPT_FILE 이 있으면 파일 내용을, 없으면 SYSTEM_PROMPT 값을 읽음.
    \\n, \\t 같은 이스케이프는 실제 개행/탭으로 변환.
    """
    prompt_file = (os.getenv("SYSTEM_PROMPT_FILE") or "").strip()
    if prompt_file:
        p = pathlib.Path(prompt_file)
        if not p.is_absolute():
            base_dir = pathlib.Path(os.path.dirname(__file__)).parent
            p = (base_dir / prompt_file).resolve()
        if p.exists():
            return p.read_text(encoding="utf-8")

    raw = os.getenv("SYSTEM_PROMPT", "").strip()
    if not raw:
        return "You are a helpful assistant."
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1]
    raw = raw.replace("\\n", "\n").replace("\\t", "\t")
    return raw


# ========== 공통 어댑터 인터페이스 ==========
class BaseGen:
    def generate(self, prompt: str, max_new_tokens: int, temperature: float, top_p: float) -> str:
        raise NotImplementedError


# ========== GGUF (llama.cpp) 백엔드 ==========
class LlamaCppAdapter(BaseGen):
    def __init__(self, repo_id: str, gguf_filename: str, cache_dir: str, token: str | None):
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        _ensure_dir(cache_dir)

        print(f"[LLM] (gguf) repo_id={repo_id}, file={gguf_filename}")
        model_path = hf_hub_download(
            repo_id=repo_id,
            filename=gguf_filename,
            token=token or None,
            cache_dir=cache_dir,
            local_dir=cache_dir,
            local_dir_use_symlinks=False,
        )

        n_threads = int(os.getenv("LLM_THREADS", str(os.cpu_count() or 4)))
        n_ctx = int(os.getenv("LLM_CTX_SIZE", "4096"))
        n_gpu_layers = int(os.getenv("LLM_N_GPU_LAYERS", "0"))

        print(f"[LLM] (gguf) path={model_path}")
        print(f"[LLM] (gguf) n_ctx={n_ctx}, n_threads={n_threads}, n_gpu_layers={n_gpu_layers}")

        self.system_prompt = _read_system_prompt()
        self.repeat_penalty = float(os.getenv("LLM_REPEAT_PENALTY", "1.1"))
        self.top_k = int(os.getenv("LLM_TOP_K", "40"))

        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            chat_format="llama-3",
        )

    def generate(self, prompt: str, max_new_tokens: int, temperature: float, top_p: float) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        out = self.llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_new_tokens,
            repeat_penalty=self.repeat_penalty,
            top_k=self.top_k,
        )
        return (out["choices"][0]["message"]["content"] or "").strip()


# ========== Hugging Face Transformers 백엔드 ==========
class TransformersAdapter(BaseGen):
    def __init__(self, model_id: str, cache_dir: str, token: str | None):
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

        _ensure_dir(cache_dir)

        dtype_map = {
            "auto": None,
            "fp32": torch.float32,
            "fp16": torch.float16,
            "bf16": torch.bfloat16,
        }
        dtype = dtype_map.get((os.getenv("HF_DTYPE") or "auto").lower(), None)

        print(f"[LLM] (hf) model_id={model_id}")
        print(
            f"[LLM] (hf) cache_dir={cache_dir}, dtype={os.getenv('HF_DTYPE','auto')}, device={os.getenv('HF_DEVICE','cpu')}"
        )

        tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            token=token or None,
            cache_dir=cache_dir,
            trust_remote_code=True,
            use_fast=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            token=token or None,
            cache_dir=cache_dir,
            trust_remote_code=True,
            torch_dtype=dtype,
            low_cpu_mem_usage=bool(int(os.getenv("HF_LOW_CPU_MEM", "1"))),
        ).eval()

        device = (os.getenv("HF_DEVICE") or "cpu").lower()
        device_map = {"": device} if device != "cuda" else "auto"

        self.pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device_map=device_map,
            torch_dtype=dtype if dtype is not None else None,
        )

        self.eos_id = self.pipe.tokenizer.eos_token_id
        if self.eos_id is None:
            cfg = getattr(self.pipe.model, "config", None)
            self.eos_id = getattr(cfg, "eos_token_id", None)

        self.system_prompt = _read_system_prompt()

    def generate(self, prompt: str, max_new_tokens: int, temperature: float, top_p: float) -> str:
        gen_kwargs = dict(
            max_new_tokens=max_new_tokens,
            return_full_text=False,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
        )
        if self.eos_id is not None:
            gen_kwargs.update(eos_token_id=self.eos_id, pad_token_id=self.eos_id)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        try:
            apply_chat_template = getattr(self.pipe.tokenizer, "apply_chat_template", None)
            if callable(apply_chat_template):
                rendered = apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                out = self.pipe(rendered, **gen_kwargs)[0]["generated_text"]
            else:
                rendered = f"{self.system_prompt}\n\n사용자: {prompt}\n어시스턴트:"
                out = self.pipe(rendered, **gen_kwargs)[0]["generated_text"]
        except Exception:
            rendered = f"{self.system_prompt}\n\n사용자: {prompt}\n어시스턴트:"
            out = self.pipe(rendered, **gen_kwargs)[0]["generated_text"]

        return (out or "").strip()


# ========== 어댑터 로더 ==========
def _load_gen():
    global _GEN
    if _GEN is not None:
        return _GEN

    token = (os.getenv("HUGGINGFACE_TOKEN") or "").strip() or None
    cache_dir = str(pathlib.Path(os.getenv("HF_CACHE_DIR") or "huggingface").resolve())
    backend = (os.getenv("LLM_BACKEND") or "gguf").lower()
    model_id = (os.getenv("HF_MODEL_ID") or "").strip()

    print(f"[LLM] backend={backend}")

    if backend == "gguf":
        gguf = (os.getenv("HF_GGUF_FILENAME") or "").strip()
        if not model_id or not gguf:
            raise RuntimeError("GGUF 모드에는 HF_MODEL_ID와 HF_GGUF_FILENAME가 필요합니다.")
        _GEN = LlamaCppAdapter(repo_id=model_id, gguf_filename=gguf, cache_dir=cache_dir, token=token)

    elif backend == "hf":
        if not model_id or model_id.lower().endswith(".gguf"):
            raise RuntimeError("HF 모드에는 Transformers 호환 HF_MODEL_ID가 필요합니다.(GGUF 불가)")
        _GEN = TransformersAdapter(model_id=model_id, cache_dir=cache_dir, token=token)

    else:
        raise RuntimeError(f"Unknown LLM_BACKEND: {backend}")

    return _GEN


# ========== Flask ==========
def create_app():
    app = Flask(__name__)

    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)

    _ = _load_gen()

    @app.get("/health")
    def health():
        return {"status": "ok", "backend": (os.getenv("LLM_BACKEND") or "gguf")}

    @app.post("/generate")
    def generate():
        data = request.get_json(silent=True) or {}
        message = (data.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        max_new_tokens = int(data.get("max_new_tokens", os.getenv("GEN_MAX_NEW_TOKENS", 256)))
        temperature = float(data.get("temperature", os.getenv("GEN_TEMPERATURE", 0.7)))
        top_p = float(data.get("top_p", os.getenv("GEN_TOP_P", 0.9)))

        gen = _load_gen()
        answer = gen.generate(message, max_new_tokens, temperature, top_p)
        return jsonify({"message": message, "answer": answer})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5150, debug=False, use_reloader=False, threaded=True)
