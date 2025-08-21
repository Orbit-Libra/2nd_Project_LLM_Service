import os
from typing import List, Dict, Any
from huggingface_hub import hf_hub_download
from huggingface_hub.utils import HfHubHTTPError
from llama_cpp import Llama
from .base import IBackend

class GGUFBackend(IBackend):
    def __init__(self, cfg: dict, env):
        self.cfg = cfg
        self.env = env
        self._llm = None
        self._model_path = None

    def name(self) -> str:
        return "gguf"

    def _resolve_token(self):
        raw = (self.env.get("HUGGINGFACE_TOKEN") or "")
        clean = raw.replace("\ufeff", "").strip().strip('"').strip("'")
        return clean if clean.startswith("hf_") else None

    def warmup(self) -> None:
        model = self.cfg["model"]
        repo_id = model["repo_id"]
        filename = model["filename"]
        cache_dir = model.get("cache_dir", None)
        token = self._resolve_token()

        # HF 다운로드 (401이면 익명 재시도)
        try:
            self._model_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                token=token,
                cache_dir=cache_dir,
                local_dir=cache_dir,
                local_dir_use_symlinks=False
            )
        except HfHubHTTPError as e:
            if getattr(e, "response", None) and e.response.status_code == 401:
                self._model_path = hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    token=None,
                    cache_dir=cache_dir,
                    local_dir=cache_dir,
                    local_dir_use_symlinks=False
                )
            else:
                raise

        lp = self.cfg.get("load_params", {})
        self._llm = Llama(
            model_path=self._model_path,
            n_ctx=int(lp.get("n_ctx", 4096)),
            n_threads=int(lp.get("n_threads", os.cpu_count() or 4)),
            n_gpu_layers=int(lp.get("n_gpu_layers", 0)),
            chat_format=lp.get("chat_format", "llama-3"),
        )

    def generate(self, messages: List[Dict[str, str]], gen_params: Dict[str, Any]) -> str:
        p = self.cfg.get("generation", {}).copy()
        p.update(gen_params or {})
        out = self._llm.create_chat_completion(
            messages=messages,
            temperature=float(p.get("temperature", 0.7)),
            top_p=float(p.get("top_p", 0.9)),
            top_k=int(p.get("top_k", 40)),
            max_tokens=int(p.get("max_new_tokens", 512)),
            repeat_penalty=float(p.get("repetition_penalty", 1.1)),
            stop=p.get("stop", []),
        )
        return (out["choices"][0]["message"]["content"] or "").strip()

    def close(self) -> None:
        self._llm = None
