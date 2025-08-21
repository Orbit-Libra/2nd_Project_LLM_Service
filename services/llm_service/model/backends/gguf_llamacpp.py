# services/llm_service/model/backends/gguf_llamacpp.py
import os
import threading
from typing import List, Dict, Any, Optional

from huggingface_hub import hf_hub_download
from huggingface_hub.utils import HfHubHTTPError
from llama_cpp import Llama

from .base import IBackend


class GGUFBackend(IBackend):
    """
    llama.cpp 기반 GGUF 백엔드
    - 단일 Llama 인스턴스에 대해 동시 호출은 thread-unsafe → 전역 락으로 직렬화
    - 과도한 max_new_tokens 방지(컨텍스트 대비 자동 클램프)
    - 충돌(OS-level access violation) 발생 시 1회 재초기화 후 재시도
    """
    def __init__(self, cfg: dict, env):
        self.cfg = cfg
        self.env = env

        self._lock = threading.Lock()
        self._llm: Optional[Llama] = None
        self._model_path: Optional[str] = None
        self._n_ctx = int(self.cfg.get("load_params", {}).get("n_ctx", 4096))
        self._llm_init_kwargs = None  # warmup 시 저장해두고, 재초기화에 재사용

    def name(self) -> str:
        return "gguf"

    # ----- utils -----
    def _resolve_token(self) -> Optional[str]:
        raw = (self.env.get("HUGGINGFACE_TOKEN") or "")
        clean = raw.replace("\ufeff", "").strip().strip('"').strip("'")
        return clean if clean.startswith("hf_") else None

    def _init_llm(self) -> None:
        """현재 self._model_path와 load_params로 llama 인스턴스 생성"""
        lp = self.cfg.get("load_params", {})
        # n_batch는 memory/속도 trade-off, Windows에서 너무 크게 잡으면 불안정해질 수 있음
        init_kwargs = dict(
            model_path=self._model_path,
            n_ctx=int(lp.get("n_ctx", 4096)),
            n_threads=int(lp.get("n_threads", os.cpu_count() or 4)),
            n_gpu_layers=int(lp.get("n_gpu_layers", 0)),
            n_batch=int(lp.get("n_batch", 256)),
            chat_format=lp.get("chat_format", "llama-3"),
        )
        # 보관(충돌 시 재초기화 용)
        self._llm_init_kwargs = init_kwargs.copy()
        self._n_ctx = init_kwargs["n_ctx"]
        self._llm = Llama(**init_kwargs)

    # ----- lifecycle -----
    def warmup(self) -> None:
        model = self.cfg["model"]
        repo_id = model["repo_id"]
        filename = model["filename"]
        cache_dir = model.get("cache_dir", None)
        token = self._resolve_token()

        # HF 다운로드 (권한 이슈 시 익명 재시도)
        try:
            self._model_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                token=token,
                cache_dir=cache_dir,
                local_dir=cache_dir,
                local_dir_use_symlinks=False,
            )
        except HfHubHTTPError as e:
            if getattr(e, "response", None) and e.response.status_code == 401:
                self._model_path = hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    token=None,
                    cache_dir=cache_dir,
                    local_dir=cache_dir,
                    local_dir_use_symlinks=False,
                )
            else:
                raise

        self._init_llm()

    def close(self) -> None:
        self._llm = None

    # ----- generation -----
    def _clamp_params(self, gen_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        cfg.generation + gen_params(override)를 병합하고,
        max_new_tokens를 n_ctx 대비 안전한 범위로 클램프
        """
        base = self.cfg.get("generation", {}).copy()
        base.update(gen_params or {})

        # 합리적인 기본값
        temperature = float(base.get("temperature", 0.7))
        top_p = float(base.get("top_p", 0.9))
        top_k = int(base.get("top_k", 40))
        rep_pen = float(base.get("repetition_penalty", 1.1))
        stop = base.get("stop", []) or []
        # 요청값 → 최소 1, 최대 n_ctx*0.4
        req_max = int(base.get("max_new_tokens", 512))
        max_allowed = max(1, int(self._n_ctx * 0.4))
        max_new = max(1, min(req_max, max_allowed))

        return {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": rep_pen,
            "max_new_tokens": max_new,
            "stop": stop,
        }

    def _call_llama(self, messages: List[Dict[str, str]], p: Dict[str, Any]) -> str:
        """
        llama 호출 (락 안에서만 호출할 것)
        """
        out = self._llm.create_chat_completion(
            messages=messages,
            temperature=p["temperature"],
            top_p=p["top_p"],
            top_k=p["top_k"],
            max_tokens=p["max_new_tokens"],
            repeat_penalty=p["repetition_penalty"],
            stop=p["stop"],
            stream=False,
        )
        return (out["choices"][0]["message"]["content"] or "").strip()

    def _retry_after_reinit(self, messages: List[Dict[str, str]], p: Dict[str, Any]) -> str:
        """
        충돌/에러 발생 시 1회 재초기화 후 더 보수적인 파라미터로 재시도
        """
        # 보수적으로 줄이기
        p2 = p.copy()
        p2["max_new_tokens"] = max(64, int(min(p["max_new_tokens"], self._n_ctx // 4)))
        p2["top_k"] = min(32, p["top_k"])
        p2["top_p"] = min(0.9, p["top_p"])
        p2["temperature"] = min(0.8, p["temperature"])

        # 재초기화
        self._init_llm()
        return self._call_llama(messages, p2)

    def generate(self, messages: List[Dict[str, str]], gen_params: Dict[str, Any]) -> str:
        if self._llm is None:
            # warmup이 아직 안 돌았다면 여기서 초기화
            self.warmup()

        p = self._clamp_params(gen_params)

        # llama.cpp는 동시 호출이 안전하지 않다 → 직렬화
        with self._lock:
            try:
                return self._call_llama(messages, p)
            except OSError as e:
                # Windows에서 access violation 시그니처 → 재초기화 후 한번 더 시도
                return self._retry_after_reinit(messages, p)
            except Exception as e:
                # ggml assert 등도 재초기화 후 1회 재시도
                return self._retry_after_reinit(messages, p)
