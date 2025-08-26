# services/llm_service/model/config_loader.py
import json
import os
import pathlib
from typing import Dict, Any, List

def _sanitize_path(s: str) -> str:
    if s is None:
        return ""
    return s.replace("\ufeff", "").strip().strip('"').strip("'")

def _candidate_paths(rel: str) -> List[pathlib.Path]:
    here = pathlib.Path(__file__).resolve()
    proj_root = here.parents[3]   # .../<project root>
    services_dir = here.parents[2]  # .../<project root>/services
    return [
        (pathlib.Path.cwd() / rel),
        (proj_root / rel),
        (services_dir / rel),
    ]

def _abs(path: str) -> pathlib.Path:
    s = _sanitize_path(path)
    p = pathlib.Path(s).expanduser()
    if p.is_absolute():
        return p

    for cand in _candidate_paths(p):
        if cand.exists():
            return cand.resolve()
    # 마지막으로 proj_root 기준 경로를 반환
    here = pathlib.Path(__file__).resolve()
    proj_root = here.parents[3]
    return (proj_root / p).resolve()

def _load_json(path: str) -> Dict[str, Any]:
    p = _abs(path)
    if not p.exists():
        # 디버깅 도움: 어떤 후보들을 검사했는지 함께 보여줌
        rel = _sanitize_path(path)
        tried = [str(c) for c in _candidate_paths(pathlib.Path(rel))]
        tried_msg = " | tried: " + " ; ".join(tried)
        raise FileNotFoundError(f"Config not found: {p}{tried_msg}")
    return json.loads(p.read_text(encoding="utf-8"))

def load_config(env: os._Environ) -> dict:
    params_path  = _sanitize_path(env.get("MODEL_PARAMS_CONFIG") or "")
    prompts_path = _sanitize_path(env.get("MODEL_PROMPTS_CONFIG") or "")
    if not params_path or not prompts_path:
        raise RuntimeError(
            "Both MODEL_PARAMS_CONFIG and MODEL_PROMPTS_CONFIG must be set "
            "(legacy single MODEL_CONFIG is not supported)."
        )

    params  = _load_json(params_path)
    prompts = _load_json(prompts_path)

    # HF cache dir env 치환
    model = params.get("model", {}) or {}
    cache_env_key = model.get("cache_dir_env")
    if cache_env_key:
        cache_dir = _sanitize_path(env.get(cache_env_key) or "")
        if cache_dir:
            model["cache_dir"] = str(pathlib.Path(cache_dir).resolve())
            params["model"] = model

    cfg = dict(params)

    # prompts 병합: 루트 또는 prompts{} 하위 모두 대응
    if isinstance(prompts.get("prompts"), dict):
        cfg["prompts"] = prompts["prompts"]
    else:
        cfg["prompts"] = {
            "roles":     prompts.get("roles", []),
            "variables": prompts.get("variables", {}),
            "snippets":  prompts.get("snippets", {}),
        }

    # 기본값 보정
    cfg.setdefault("generation", {})
    cfg.setdefault("policy", {})
    cfg.setdefault("multiturn", {})

    return cfg
