# model/backends/hf_transformers.py

from typing import List, Dict, Any
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from .base import IBackend

class HFBackend(IBackend):
    def __init__(self, cfg: dict, env):
        self.cfg = cfg
        self.env = env
        self.pipe = None
        self._model_id = cfg["model"]["repo_id"]

    def name(self) -> str:
        return "hf"

    def warmup(self) -> None:
        lp = self.cfg.get("load_params", {})
        dtype_map = {"auto": None, "fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}
        dtype = dtype_map.get(str(lp.get("dtype", "auto")).lower(), None)
        device = str(lp.get("device", "cpu")).lower()

        tok = AutoTokenizer.from_pretrained(self._model_id, trust_remote_code=True, use_fast=True)
        mdl = AutoModelForCausalLM.from_pretrained(
            self._model_id, trust_remote_code=True, torch_dtype=dtype,
            low_cpu_mem_usage=bool(lp.get("low_cpu_mem_usage", True))
        ).eval()

        device_map = {"": device} if device != "cuda" else "auto"
        self.pipe = pipeline("text-generation", model=mdl, tokenizer=tok,
                             device_map=device_map, torch_dtype=dtype if dtype else None)
        self.eos_id = self.pipe.tokenizer.eos_token_id or getattr(getattr(self.pipe.model, "config", None), "eos_token_id", None)

    def generate(self, messages: List[Dict[str, str]], gen_params: Dict[str, Any]) -> str:
        p = self.cfg.get("generation", {}).copy()
        p.update(gen_params or {})

        # chat template 지원 시 활용
        apply_chat_template = getattr(self.pipe.tokenizer, "apply_chat_template", None)
        if callable(apply_chat_template):
            rendered = apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            # fallback
            rendered = "\n".join([f"{m['role']}: {m['content']}" for m in messages]) + "\nassistant:"

        gen_kwargs = dict(
            max_new_tokens=int(p.get("max_new_tokens", 512)),
            return_full_text=False,
            do_sample=bool(p.get("do_sample", True)),
            temperature=float(p.get("temperature", 0.7)),
            top_p=float(p.get("top_p", 0.9))
        )
        if getattr(self, "eos_id", None) is not None:
            gen_kwargs.update(eos_token_id=self.eos_id, pad_token_id=self.eos_id)

        out = self.pipe(rendered, **gen_kwargs)[0]["generated_text"]
        return (out or "").strip()

    def close(self) -> None:
        self.pipe = None
