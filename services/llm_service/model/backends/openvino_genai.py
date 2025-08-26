import os
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

from huggingface_hub import snapshot_download, login
from openvino_genai import LLMPipeline, GenerationConfig

# ⬇️ NPU/디바이스 인식 로그용 (신규 API 우선)
try:
    from openvino import Core  # 권장 (openvino.runtime는 deprecated 경고)
    _OV_CORE_AVAILABLE = True
except Exception:
    try:
        from openvino.runtime import Core  # fallback
        _OV_CORE_AVAILABLE = True
    except Exception:
        _OV_CORE_AVAILABLE = False

from .base import IBackend


class OVGenAIBackend(IBackend):
    """
    OpenVINO GenAI LLM 백엔드
    - params.json의 값들을 1순위로 사용
    - HUGGINGFACE_TOKEN만 .env에서 읽음(선택)
    - NPU 우선(device="AUTO:NPU,CPU"), 실패/부재 시 CPU 폴백
    - HF 레포가 IR(OpenVINO) 형식이면 변환 없이 그대로 사용
    """

    def __init__(self, cfg: dict, env):
        self.cfg = cfg or {}
        self.env = env
        self._lock = threading.Lock()
        self._pipe: Optional[LLMPipeline] = None
        self._model_dir: Optional[Path] = None

        self.log = logging.getLogger("ov_genai")
        if not self.log.handlers:
            self.log.setLevel(logging.INFO)

    def name(self) -> str:
        return "ov_genai"

    # ---------- helpers ----------
    def _format_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        OV GenAI LLMPipeline.generate 는 str 또는 list[str] 만 허용.
        list[dict] 형태(역할/콘텐츠)를 간단한 프롬프트로 직렬화한다.
        모델/템플릿별로 조정 가능. (현재는 안전한 범용 포맷)
        """
        sys_parts = [m["content"] for m in messages if m.get("role") == "system" and m.get("content")]
        user_assistant = []
        for m in messages:
            role = m.get("role")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                user_assistant.append(f"User: {content}")
            elif role == "assistant":
                user_assistant.append(f"Assistant: {content}")

        prompt_lines = []
        if sys_parts:
            # 시스템 프롬프트는 한 블록으로
            sys_text = "\n".join(sys_parts)
            prompt_lines.append(f"System: {sys_text}")
            prompt_lines.append("")  # 빈 줄

        prompt_lines.extend(user_assistant)
        # 마지막에 어시스턴트 답변을 유도
        prompt_lines.append("Assistant:")

        prompt = "\n".join(prompt_lines).strip()
        # (선택) 너무 긴 시스템 프롬프트를 잘라내고 싶으면 여기서 제한 가능
        return prompt
    
    def _get(self, dct: dict, key: str, default=None):
        v = dct.get(key, default) if isinstance(dct, dict) else default
        if isinstance(v, str):
            return v.replace("\ufeff", "").strip().strip('"').strip("'")
        return v

    def _resolve_cache(self) -> Path:
        # 우선순위: params.json > .env(HF_CACHE_DIR) > 기본값
        model = self._get(self.cfg, "model", {})
        cache_dir = self._get(model, "cache_dir", None) \
                    or self.env.get("HF_CACHE_DIR") \
                    or "services/llm_service/huggingface"
        path = Path(cache_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _hf_login_if_needed(self):
        tok = (self.env.get("HUGGINGFACE_TOKEN") or "").strip().strip('"').strip("'")
        if tok.startswith("hf_"):
            try:
                # git credential 저장은 끔(윈도우에서 경로 경고 방지)
                login(token=tok, add_to_git_credential=False)
            except Exception as e:
                self.log.warning(f"[OV] HF login skipped due to error: {e!r}")

    def _export_if_needed(self, hf_id: str, export_precision: str, cache: Path) -> Path:
        """
        - IR 레포(openvino_model.xml/bin 존재)면: 레포 디렉터리(repo_dir)를 그대로 반환
        - PT 레포면: optimum-intel로 IR export 후 ov_root 경로 반환
        """
        # 1) HF snapshot
        repo_dir = Path(snapshot_download(
            repo_id=hf_id,
            local_dir=cache / "hf_snapshots",
            token=(self.env.get("HUGGINGFACE_TOKEN") or None)
        ))

        # 2) IR 레포인지 확인
        if (repo_dir / "openvino_model.xml").exists() and (repo_dir / "openvino_model.bin").exists():
            self.log.info(f"[OV] IR repo detected. Using IR at: {repo_dir}")
            return repo_dir

        # 3) PT 레포 → IR export
        ov_root = cache / "ov_models" / hf_id.replace("/", "__") / export_precision
        xml = ov_root / "openvino_model.xml"
        if xml.exists():
            self.log.info(f"[OV] Reusing exported IR at: {ov_root}")
            return ov_root

        from optimum.intel import OVModelForCausalLM
        from transformers import AutoTokenizer

        ov_root.mkdir(parents=True, exist_ok=True)

        # 토크나이저 저장 (fast 강제 X)
        try:
            tok = AutoTokenizer.from_pretrained(repo_dir.as_posix(), use_fast=False)
            tok.save_pretrained(ov_root.as_posix())
        except Exception as e:
            self.log.warning(f"[OV] Tokenizer save skipped: {e!r}")

        ov_kwargs = dict(export=True, compile=False)
        try:
            if export_precision:
                ov_kwargs["weight_format"] = export_precision  # e.g. "int4_sym","int8","fp16"
            ov_model = OVModelForCausalLM.from_pretrained(repo_dir.as_posix(), **ov_kwargs)
        except TypeError:
            ov_model = OVModelForCausalLM.from_pretrained(repo_dir.as_posix(), export=True, compile=False)

        ov_model.save_pretrained(ov_root.as_posix())
        self.log.info(f"[OV] Exported IR to: {ov_root} (precision={export_precision})")
        return ov_root

    def _log_detected_devices(self):
        """OpenVINO가 인식한 디바이스 목록을 1회 로깅."""
        if not _OV_CORE_AVAILABLE:
            self.log.warning("[OV] Core import failed; cannot list devices.")
            return
        try:
            ie = Core()
            devices = ie.available_devices  # 예: ['CPU', 'GPU', 'NPU']
            self.log.info(f"[OV] Detected devices: {devices}")
        except Exception as e:
            self.log.warning(f"[OV] Failed to query available_devices: {e!r}")

    def _build_pipeline(self):
        model = self._get(self.cfg, "model", {})
        loadp = self._get(self.cfg, "load_params", {})

        hf_id = self._get(model, "hf_model_id")
        if not hf_id:
            raise RuntimeError("ov_genai: 'model.hf_model_id' is required in params.json")

        export_precision = self._get(model, "export_precision", "int4_sym")
        device = self._get(loadp, "device", None) \
                 or os.getenv("OV_DEVICE") \
                 or "AUTO:NPU,CPU"

        cache = self._resolve_cache()
        self._hf_login_if_needed()

        # 디바이스/모델 로깅
        self._log_detected_devices()
        self.log.info(f"[OV] OV_DEVICE env={os.getenv('OV_DEVICE')!r}, using device='{device}'")
        self.log.info(f"[OV] HF model id='{hf_id}', export_precision='{export_precision}'")

        # 모델 경로 해석 (IR 레포면 repo_dir 그대로 반환)
        self._model_dir = self._export_if_needed(hf_id, export_precision, cache)

        self.log.info(f"[OV] Loading LLMPipeline from: {self._model_dir.as_posix()}")

        # 컴파일(로드) 시도 + 장치 폴백(장치 관련 실패 시)
        try:
            self._pipe = LLMPipeline(self._model_dir.as_posix(), device)
            self.log.info(f"[OV] LLMPipeline ready on device='{device}'")
        except Exception as e:
            self.log.warning(f"[OV] Pipeline build failed on '{device}', reason={e!r}")
            # 장치 이슈일 수 있으니 CPU로 1회 폴백 시도
            # (그래프/IR 자체 shape 오류면 CPU도 실패할 수 있음)
            try:
                self._pipe = LLMPipeline(self._model_dir.as_posix(), "CPU")
                self.log.info("[OV] LLMPipeline ready on device='CPU' (fallback)")
            except Exception as e2:
                self.log.error(f"[OV] Pipeline build failed on CPU as well. reason={e2!r}")
                raise  # 더 이상 진행 불가 → 예외 전파

    def warmup(self) -> None:
        if self._pipe is None:
            self._build_pipeline()

    def close(self) -> None:
        self._pipe = None

    # ---------- generation ----------
    def _gen_cfg_from(self, overrides: Dict[str, Any]) -> GenerationConfig:
        gen = self._get(self.cfg, "generation", {}) or {}

        def pick(k, default):
            if k in overrides and overrides[k] is not None:
                return overrides[k]
            return self._get(gen, k, default)

        return GenerationConfig(
            max_new_tokens=int(pick("max_new_tokens", 180)),
            temperature=float(pick("temperature", 0.5)),
            top_p=float(pick("top_p", 0.9)),
            top_k=int(pick("top_k", 40)),
        )
        # stop 문자열은 OV GenAI 파이프라인에서 별도 인자로 처리하지 않음(룰 레벨에서 컷)

    def generate(self, messages: List[Dict[str, str]], gen_params: Dict[str, Any]) -> str:
        if self._pipe is None:
            self.warmup()

        cfg = self._gen_cfg_from(gen_params or {})
        # ✅ list[dict] → str 로 변환
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            prompt = self._format_messages_to_prompt(messages)
        elif isinstance(messages, str):
            prompt = messages
        elif isinstance(messages, list) and messages and isinstance(messages[0], str):
            prompt = "\n".join(messages)  # list[str]도 허용되지만 안전하게 합치기
        else:
            # 방어: 알 수 없는 입력
            prompt = str(messages)

        with self._lock:
            try:
                out = self._pipe.generate(prompt, cfg)
                return (out if isinstance(out, str) else str(out)).strip()
            except Exception as e:
                self.log.warning(f"[OV] Generation failed on current device; fallback to CPU. reason={e!r}")
                try:
                    self._pipe = LLMPipeline(self._model_dir.as_posix(), "CPU")
                    out = self._pipe.generate(prompt, cfg)
                    return (out if isinstance(out, str) else str(out)).strip()
                except Exception as e2:
                    self.log.error(f"[OV] Generation failed on CPU fallback. reason={e2!r}")
                    raise
