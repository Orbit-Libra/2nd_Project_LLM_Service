# services/llm_service/model/router.py
import re
from typing import List, Dict, Any

from .prompts import render_messages
from .backends.gguf_llamacpp import GGUFBackend
from .backends.hf_transformers import HFBackend
from ..chains.base_chat_chain import build_base_chat_chain  # LCEL 체인


class ModelRouter:
    """
    기존 인터페이스를 유지하면서 내부에 LangChain(LCEL) 체인을 끼운 라우터.
    - generate(): 문자열 입력 -> 문자열 출력(호환)
    - generate_messages(): 역할 메시지 배열을 직접 전달(LCEL 우회)
    - generate_structured(): LCEL 구조화 응답(dict) 반환
    """
    def __init__(self, backend, cfg: dict):
        self._backend = backend
        self._cfg = cfg
        self._backend.warmup()
        self._chain = self._build_chain()

    def _build_chain(self):
        def _backend_generate(messages, gen_params):
            return self._backend.generate(messages, gen_params or {})
        return build_base_chat_chain(_backend_generate, self._cfg)

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

    # ✅ 고정 길이 look-behind만 사용 (영/한 문장부호 뒤 공백)
    _SENT_SPLIT = re.compile(r'(?<=[.!?。！？])\s+')

    def _postprocess(self, text: str, overrides: Dict[str, Any] | None = None) -> str:
        """
        요청별 overrides 우선 적용:
          - enforce_max_lines: 줄 수 컷
          - enforce_max_sentences: 문장 수 컷
          - enforce_max_chars: 글자 수 컷
          - force_suffix: 각 줄 접미사
        순서: 글자 컷 -> 문장 컷 -> 줄 컷 -> 접미사
        """
        policy = self._cfg.get("policy", {}) or {}
        ovr = overrides or {}

        max_chars = int(ovr.get("enforce_max_chars", 0) or 0)
        max_sents = int(ovr.get("enforce_max_sentences", 0) or 0)
        max_lines = int(ovr.get("enforce_max_lines", policy.get("enforce_max_lines", 0) or 0))
        suffix = ovr.get("force_suffix", policy.get("force_suffix", "") or "")

        text = (text or "").strip()

        # 1) 글자 컷
        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars].rstrip() + "…"

        # 2) 문장 컷
        if max_sents > 0:
            parts = self._SENT_SPLIT.split(text)
            if len(parts) > max_sents:
                text = " ".join(parts[:max_sents]).strip()

        # 3) 줄 컷
        if max_lines > 0:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            text = "\n".join(lines[:max_lines])

        # 4) 접미사
        if suffix:
            lines = text.splitlines() or [text]
            lines = [ln if ln.endswith(suffix) else (ln.rstrip() + " " + suffix) for ln in lines]
            text = "\n".join(lines).strip()

        return text

    def generate(self, user_text: str, overrides: Dict[str, Any] | None = None) -> str:
        payload = {"message": user_text, "overrides": overrides or {}}
        out = self._chain.invoke(payload)  # {"answer": "...", ...}
        return self._postprocess(out.get("answer", ""), overrides)

    def generate_messages(self, messages: List[Dict[str, str]], overrides: Dict[str, Any] | None = None) -> str:
        result = self._backend.generate(messages, overrides or {})
        return self._postprocess(result, overrides)

    def generate_structured(self, user_text: str, overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload = {"message": user_text, "overrides": overrides or {}}
        out = self._chain.invoke(payload)
        if isinstance(out, dict):
            out.setdefault("answer", "")
            out.setdefault("summary", None)
            out.setdefault("citations", [])
            out["answer"] = (out["answer"] or "").strip()
            return out
        return {"answer": str(out).strip(), "summary": None, "citations": []}

    def build_messages(self, conversation: List[Dict[str, str]] | None, user_text: str) -> List[Dict[str, str]]:
        """gguf.json 기본 system 메시지 + 대화 컨텍스트 + 현재 질문 조합"""
        prompts = self._cfg.get("prompts", {})
        roles = prompts.get("roles", [])
        variables = prompts.get("variables", {})
        base = render_messages(roles, variables)
        conv = conversation or []
        return base + conv + [{"role": "user", "content": user_text}]
