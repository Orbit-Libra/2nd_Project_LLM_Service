# services/llm_service/chains/base_chat_chain.py
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import PydanticOutputParser


# === 1) 정형 출력 스키마 (structured 모드에서만 사용) ===
class LibraReply(BaseModel):
    answer: str = Field(..., description="최종 한국어 답변(간결)")
    summary: str | None = Field(default=None, description="한 줄 요약(선택)")
    citations: list[str] = Field(default_factory=list, description="근거 ID 리스트(선택)")


# === 2) gguf.json roles -> ChatPromptTemplate 튜플 ===
def _roles_to_prompt_tuples(roles: List[Dict[str, str]]) -> List[tuple[str, str]]:
    tuples: List[tuple[str, str]] = []
    for r in roles or []:
        role = (r.get("role") or "system").lower()
        content = r.get("content", "")
        if role == "user":
            lc_role = "human"
        elif role == "assistant":
            lc_role = "ai"
        else:
            lc_role = "system"
        tuples.append((lc_role, content))
    return tuples


# === 3) LC 메시지 -> llama.cpp 메시지 ===
def _lcmsgs_to_llama(msgs: List[BaseMessage]) -> List[Dict[str, str]]:
    out = []
    for m in msgs:
        t = getattr(m, "type", "system")  # "system"|"human"|"ai"
        role = "user" if t == "human" else ("assistant" if t == "ai" else "system")
        out.append({"role": role, "content": m.content})
    return out


def build_base_chat_chain(backend_generate_fn, cfg: Dict[str, Any]):
    """
    backend_generate_fn(messages, gen_params) -> str
    입력 페이로드: {"message": "...", "overrides": {...}}
    - 기본: 빠른 경로 (형식 지시문/파서 없음)
    - overrides.structured=True 일 때만 짧은 JSON 지시문 + 파서 사용
    """
    prompts_cfg = cfg.get("prompts") or {}
    roles: List[Dict[str, str]] = prompts_cfg.get("roles", []) or []
    variables: Dict[str, Any] = prompts_cfg.get("variables", {}) or {}

    # 정책(후처리)은 최소화: 여기선 줄 수/접미사만 적용
    policy = (cfg.get("policy") or {})
    max_lines = int(policy.get("enforce_max_lines", 0))
    force_suffix = policy.get("force_suffix")

    pyd_parser = PydanticOutputParser(pydantic_object=LibraReply)

    def render(inp: Dict[str, Any]) -> Dict[str, Any]:
        overrides = inp.get("overrides", {}) or {}
        structured = bool(overrides.get("structured", False))

        base_tuples = _roles_to_prompt_tuples(roles)
        if structured:
            # ✨ 짧은 JSON 지시문 (장문의 format_instructions 사용 안 함)
            brief_json_rule = (
                '다음 JSON 스키마로만 출력:\n'
                '{"answer": "문장", "summary": "문장|null", "citations": ["id"...]}\n'
                '설명/코드블록/추가텍스트 금지, JSON만 출력.'
            )
            tuples = base_tuples + [("human", "{message}\n\n" + brief_json_rule)]
        else:
            tuples = base_tuples + [("human", "{message}")]

        prompt = ChatPromptTemplate.from_messages(tuples)
        fmt_vars = {**variables, **inp}
        msgs = prompt.format_messages(**fmt_vars)
        return {"lc_msgs": msgs, "overrides": overrides, "structured": structured}

    def call_backend(packed: Dict[str, Any]) -> Dict[str, Any]:
        text = backend_generate_fn(
            messages=_lcmsgs_to_llama(packed["lc_msgs"]),
            gen_params=packed.get("overrides", {}) or {}
        )
        return {"text": text, "structured": packed.get("structured", False)}

    def parse_out(packed: Dict[str, Any]) -> Dict[str, Any]:
        txt = (packed.get("text") or "").strip()
        if packed.get("structured", False):
            # 파싱 시도 (실패해도 안전 래핑)
            try:
                obj = pyd_parser.parse(txt)
                if isinstance(obj, dict):
                    d = obj
                else:
                    d = obj.dict()
            except Exception:
                d = {"answer": txt, "summary": None, "citations": []}
        else:
            d = {"answer": txt, "summary": None, "citations": []}
        return d

    def apply_policy(d: Dict[str, Any]) -> Dict[str, Any]:
        txt = (d.get("answer") or "").strip()
        if max_lines > 0:
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            txt = "\n".join(lines[:max_lines])
        if force_suffix:
            lines = [
                ln if ln.endswith(force_suffix) else (ln.rstrip() + " " + force_suffix)
                for ln in (txt.splitlines() or [txt])
            ]
            txt = "\n".join(lines).strip()
        d["answer"] = txt
        return d

    # === LCEL ===
    chain = (
        RunnablePassthrough()          # {"message": "...", "overrides": {...}}
        | RunnableLambda(render)       # -> {"lc_msgs":[...], "overrides":..., "structured":bool}
        | RunnableLambda(call_backend) # -> {"text": "...", "structured":bool}
        | RunnableLambda(parse_out)    # -> dict
        | RunnableLambda(apply_policy) # -> dict
    )
    return chain
