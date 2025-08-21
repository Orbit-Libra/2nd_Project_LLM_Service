from typing import List, Dict, Any
from .prompts import render_messages
from .backends.gguf_llamacpp import GGUFBackend
from .backends.hf_transformers import HFBackend

class ModelRouter:
    def __init__(self, backend, cfg: dict):
        self._backend = backend
        self._cfg = cfg
        self._backend.warmup()

    @classmethod
    def from_config(cls, cfg: dict, env) -> "ModelRouter":
        backend_name = cfg.get("backend", "gguf").lower()
        if backend_name == "gguf":
            backend = GGUFBackend(cfg, env)
        elif backend_name == "hf":
            backend = HFBackend(cfg, env)
        else:
            raise RuntimeError(f"Unsupported backend: {backend_name}")
        return cls(backend, cfg)

    @property
    def backend_name(self) -> str:
        return self._cfg.get("backend", "unknown")

    @property
    def model_name(self) -> str:
        return self._cfg.get("name", "unknown")

    def _postprocess(self, text: str) -> str:
        policy = self._cfg.get("policy", {})
        max_lines = int(policy.get("enforce_max_lines", 0))
        if max_lines > 0:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            text = "\n".join(lines[:max_lines])
        suffix = policy.get("force_suffix")
        if suffix:
            # 각 줄 끝에 접미사 없으면 추가
            lines = [ln if ln.endswith(suffix) else (ln.rstrip() + " " + suffix) for ln in text.splitlines() or [text]]
            text = "\n".join(lines)
        return text.strip()

    def generate(self, user_text: str, overrides: Dict[str, Any] | None = None) -> str:
        prompts = self._cfg.get("prompts", {})
        roles = prompts.get("roles", [])
        variables = prompts.get("variables", {})
        messages = render_messages(roles, variables) + [{"role": "user", "content": user_text}]
        result = self._backend.generate(messages, overrides or {})
        return self._postprocess(result)
    
    def generate_messages(self, messages: List[Dict[str, str]], overrides: Dict[str, Any] | None = None) -> str:
        result = self._backend.generate(messages, overrides or {})
        return self._postprocess(result)