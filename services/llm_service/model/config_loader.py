import json
import os
import pathlib

def load_config(config_path: str, env: os._Environ) -> dict:
    p = pathlib.Path(config_path)
    if not p.is_absolute():
        # server.py 기준 프로젝트 루트 상대경로 지원
        base = pathlib.Path(__file__).resolve().parents[2]
        p = (base / config_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")

    cfg = json.loads(p.read_text(encoding="utf-8"))

    # env 병합: cache_dir_env -> 실제 경로 치환, 토큰 삽입 등
    model = cfg.get("model", {})
    cache_env_key = model.get("cache_dir_env")
    if cache_env_key:
        cache_dir = env.get(cache_env_key, "")
        if cache_dir:
            model["cache_dir"] = str(pathlib.Path(cache_dir).resolve())
            cfg["model"] = model

    # 기본값 보정
    cfg.setdefault("generation", {})
    cfg.setdefault("prompts", {"roles": [], "variables": {}})
    cfg.setdefault("policy", {})

    return cfg
