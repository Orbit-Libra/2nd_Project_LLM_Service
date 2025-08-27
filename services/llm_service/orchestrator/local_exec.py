# services/llm_service/orchestrator/local_exec.py
import logging
from typing import Dict, Any, List
from services.llm_service.chains.user_data_chain import build_user_data_chain
from services.llm_service.model.prompts import render_messages

log = logging.getLogger("orchestrator.local")

# ===== 공통 유틸 =====
def _get_cfg(cfg: dict, path: List[str], default=None):
    cur = cfg
    for p in path:
        cur = (cur or {}).get(p, {})
    return cur or default

def apply_generation_defaults(cfg: dict, overrides: dict) -> dict:
    gen = cfg.get("generation", {})
    ov = dict(overrides or {})
    ov.setdefault("max_new_tokens", int(gen.get("max_new_tokens", 180)))
    ov.setdefault("temperature", float(gen.get("temperature", 0.7)))
    ov.setdefault("top_p", float(gen.get("top_p", 0.9)))
    ov.setdefault("top_k", int(gen.get("top_k", 40)))
    ov.setdefault("enforce_max_sentences", 3)
    ov.setdefault("enforce_max_chars", 300)
    return ov

def apply_output_policy(cfg: dict, text: str) -> str:
    pol = cfg.get("policy", {})
    if not text:
        return text
    max_lines = int(pol.get("enforce_max_lines", 0))
    if max_lines > 0:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        text = "\n".join(lines[:max_lines])
    suffix = pol.get("force_suffix", "")
    if suffix:
        lines = text.splitlines() if text else [text]
        lines = [ln if ln.endswith(suffix) else (ln.rstrip() + " " + suffix) for ln in lines]
        text = "\n".join(lines).strip()
    return text

def build_base_messages(cfg: dict, runtime_vars: dict | None = None):
    prompts = cfg.get("prompts", {})
    roles = prompts.get("roles", [])
    variables = prompts.get("variables", {})
    merged = {**variables, **(runtime_vars or {})}
    return render_messages(roles, merged)

def extract_affiliation_override(text: str) -> str | None:
    import re
    m = re.search(r'([가-힣A-Za-z]+대학교)', text or "")
    return m.group(1) if m else None

# ===== 경로 1: 게스트 베이스 챗 =====
def run_guest_base_chat(router, cfg: dict, user_text: str, overrides: dict) -> str:
    base = build_base_messages(cfg, {"user_name": "게스트", "salutation_prefix": "", "user_affiliation": ""})
    gk_hint = ((cfg.get("prompts", {}).get("snippets", {}) or {}).get("general_knowledge_hint") or "")
    concise_rule = ((cfg.get("prompts", {}).get("snippets", {}) or {}).get("concise_rule") or "")
    safety_rule = (
        "정확히 알지 못하는 내용은 추측하지 말고 '잘 모르겠습니다'라고 답하라. "
        "특히 전문적이거나 최신 정보가 필요한 질문에는 신중하게 답하라."
    )
    messages = base + []
    if gk_hint: messages.append({"role": "system", "content": gk_hint})
    messages.append({"role": "system", "content": safety_rule})
    if concise_rule: messages.append({"role": "system", "content": concise_rule})
    messages.append({"role": "user", "content": user_text})
    ov = apply_generation_defaults(cfg, overrides)
    body = router.generate_messages(messages, overrides=ov)
    return apply_output_policy(cfg, body)

# ===== 경로 2: 로그인 사용자 - 로컬 유저데이터 체인 =====
_user_chain_singleton = None

def run_user_local(router, cfg: dict, repo, usr_id: str, user_text: str, overrides: dict):
    global _user_chain_singleton
    if _user_chain_singleton is None:
        _user_chain_singleton = build_user_data_chain(router.generate_messages, cfg)
        log.info("user_data_chain 초기화 완료")

    try:
        prof = repo.get_user_profile(usr_id)
    except Exception as e:
        raise RuntimeError(f"DB error(get_user_profile): {e}")

    usr_name, usr_snm = prof if prof else ("사용자", "미상")
    salutation_prefix = f"{usr_name}님, "
    aff_override = extract_affiliation_override(user_text)
    aff_to_use = (aff_override or usr_snm or "")

    chain_input = {
        "message": user_text,
        "usr_id": usr_id,
        "user_name": usr_name,
        "salutation_prefix": salutation_prefix,
        "user_affiliation": aff_to_use,
        "overrides": apply_generation_defaults(cfg, overrides)
    }
    result = _user_chain_singleton.invoke(chain_input)
    body = result.get("answer", "답변을 생성할 수 없습니다.")
    body = apply_output_policy(cfg, body)
    return body, {"usr_name": usr_name, "usr_snm": usr_snm, "salutation_prefix": salutation_prefix, "aff_to_use": aff_to_use}

# ===== 경로 3: 로그인 사용자 - 일반 베이스 챗(로컬) =====
def run_user_base_chat(router, cfg: dict, repo, usr_id: str, conv_id: int, user_text: str, overrides: dict):
    try:
        prof = repo.get_user_profile(usr_id)
    except Exception as e:
        raise RuntimeError(f"DB error(get_user_profile): {e}")

    usr_name, usr_snm = prof if prof else ("사용자", "미상")
    salutation_prefix = f"{usr_name}님, "

    hist = repo.fetch_history(conv_id, limit=int((cfg.get("multiturn") or {}).get("context_turns", 6)) + 2)
    if hist and hist[-1].get("role") == "user":
        hist = hist[:-1]

    gk_hint = ((cfg.get("prompts", {}).get("snippets", {}) or {}).get("general_knowledge_hint") or "")
    concise_rule = ((cfg.get("prompts", {}).get("snippets", {}) or {}).get("concise_rule") or "")
    focus_rule = "현재 질문에만 정확히 답하고 확실하지 않으면 '잘 모르겠습니다'라고 답하라."

    aff_override = extract_affiliation_override(user_text)
    aff_to_use = (aff_override or usr_snm or "")

    base = build_base_messages(cfg, {"user_name": usr_name, "salutation_prefix": salutation_prefix, "user_affiliation": aff_to_use})
    messages = base + []
    if gk_hint: messages.append({"role": "system", "content": gk_hint})
    messages.append({"role": "system", "content": focus_rule})
    if len(hist) > 0:
        recent = hist[-1]
        if recent.get("role") in ("user", "assistant"):
            messages.append({"role": recent["role"], "content": recent.get("content", "")[:300]})
    if concise_rule: messages.append({"role": "system", "content": concise_rule})
    messages.append({"role": "user", "content": user_text})

    ov = apply_generation_defaults(cfg, overrides)
    body = router.generate_messages(messages, overrides=ov)
    body = apply_output_policy(cfg, body)
    return body, {"usr_name": usr_name, "usr_snm": usr_snm, "salutation_prefix": salutation_prefix, "aff_to_use": aff_to_use}
