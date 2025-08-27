import logging, os
from .schemas import OrchestratorInput, OrchestratorOutput
from . import intent_classifier, local_exec, planner, agent_client

log = logging.getLogger("orchestrator")
ilog = logging.getLogger("orchestrator.intent")

AGENT_ENABLED = os.getenv("AGENT_ENABLED", "false").lower() == "true"


def _format_rag_snippets(matches, max_chars=1400, max_items=5) -> str:
    """에이전트가 준 RAG 매치들을 시스템 컨텍스트로 정리"""
    items = (matches or [])[:max_items]
    lines = ["[USAGE GUIDE SNIPPETS]"]
    used = 0
    for i, m in enumerate(items, 1):
        if isinstance(m, str):
            txt, meta, score = m.strip(), {}, None
        else:
            txt = (m.get("text") or "").strip()
            meta = m.get("meta") or {}
            score = m.get("score")
        if not txt:
            continue
        page = meta.get("page")
        head = f"- #{i} (p.{page})" if page else f"- #{i}"
        chunk = f"{head} {txt}"
        if used + len(chunk) > max_chars:
            break
        lines.append(chunk)
        used += len(chunk)
    return "\n".join(lines)


def _synthesize_from_rag(router, cfg, query: str, rag: dict, overrides: dict, usr_name="게스트", usr_snm=""):
    base = local_exec.build_base_messages(cfg, {
        "user_name": usr_name,
        "salutation_prefix": "",
        "user_affiliation": usr_snm or ""
    })
    concise_rule = ((cfg.get("prompts", {}).get("snippets", {}) or {}).get("concise_rule") or "")
    sys_rule = (
        "아래 문서 스니펫만 근거로, 질문에 정확히 답하라. "
        "스니펫에 없는 정보는 추측하지 말고 '정확히 알지 못합니다'라고 답하라. "
        "불필요한 배경설명 없이 간결하게."
    )
    snippets = _format_rag_snippets((rag or {}).get("matches") or [])

    messages = list(base)
    messages.append({"role": "system", "content": sys_rule})
    if snippets:
        messages.append({"role": "system", "content": snippets})
    if concise_rule:
        messages.append({"role": "system", "content": concise_rule})
    messages.append({"role": "user", "content": query})

    ov = local_exec.apply_generation_defaults(cfg, overrides or {})
    body = router.generate_messages(messages, overrides=ov)
    return local_exec.apply_output_policy(cfg, body)


def _extract_rag_blob(res: dict) -> dict | None:
    """
    에이전트 응답에서 RAG 결과를 최대한 관대하게 찾는다.
    지원 형태:
      - top-level: {"rag": {...}}, {"context_snippets": [...]}, {"matches":[...]}
      - nested: {"data":{"rag":{...}}}, {"data":{"result":{...}}}, {"result":{...}}, {"tool_result":{...}}
      - Chroma raw: {"documents":[[...]], "metadatas":[[...]], "distances":[[...]]}
    """
    if not isinstance(res, dict):
        return None

    # 0) 가장 흔한 커스텀 키
    if isinstance(res.get("context_snippets"), list):
        cs = res["context_snippets"]
        # 이미 {"text":...} 형태면 그대로, 문자열 리스트면 변환
        matches = []
        for x in cs:
            if isinstance(x, str):
                matches.append({"text": x, "meta": {}, "score": None})
            elif isinstance(x, dict) and ("text" in x or "chunk" in x):
                txt = x.get("text") or x.get("chunk") or ""
                meta = x.get("meta") or {}
                score = x.get("score")
                matches.append({"text": txt, "meta": meta, "score": score})
        if matches:
            return {"matches": matches}

    # 1) 널리 쓰일 법한 경로들
    cand_paths = [
        ["rag"],
        ["data", "rag"],
        ["data", "result"],
        ["result"],
        ["tool_result", "rag"],
        ["tool_result"],
    ]

    def dig(d: dict, path: list[str]):
        cur = d
        for key in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        return cur

    for p in cand_paths:
        blob = dig(res, p)
        if isinstance(blob, dict):
            # 표준 matches
            if isinstance(blob.get("matches"), list):
                return {"matches": blob["matches"]}
            # chroma raw → matches 정규화
            docs = blob.get("documents")
            metas = blob.get("metadatas")
            dists = blob.get("distances")
            if isinstance(docs, list) and isinstance(metas, list):
                docs0 = docs[0] if docs and isinstance(docs[0], list) else docs
                metas0 = metas[0] if metas and isinstance(metas[0], list) else metas
                dists0 = dists[0] if dists and isinstance(dists[0], list) else dists
                matches = []
                for i, d in enumerate(docs0):
                    m = metas0[i] if i < len(metas0) else {}
                    s = float(dists0[i]) if dists0 and i < len(dists0) else None
                    matches.append({"text": d, "meta": m, "score": s})
                if matches:
                    return {"matches": matches}
        if isinstance(blob, list) and blob and isinstance(blob[0], dict) and "text" in blob[0]:
            return {"matches": blob}

    # 2) 최후: top-level에 matches가 바로 있는 경우
    if isinstance(res.get("matches"), list):
        return {"matches": res["matches"]}

    return None


def handle(router, cfg: dict, repo, inp: OrchestratorInput) -> OrchestratorOutput:
    intent = intent_classifier.classify(inp.query, inp.usr_id)
    ilog.info(
        "[INTENT] usr_id=%r conv_id=%r kind=%s reason=%s slots=%d calc=%s external=%s",
        inp.usr_id, inp.conv_id,
        intent.kind, intent.reason,
        len(intent.user_slots or []),
        intent.wants_calculation,
        intent.external_entities,
    )

    if intent.kind == "guest_base_chat":
        log.info("[PATH] route=guest_base_chat")
        body = local_exec.run_guest_base_chat(router, cfg, inp.query, inp.overrides)
        return OrchestratorOutput(answer=body, route="guest_base_chat", meta={"intent": intent.dict()})

    if intent.kind == "user_local":
        log.info("[PATH] route=local_user (user_data_chain)")
        body, prof = local_exec.run_user_local(router, cfg, repo, inp.usr_id, inp.query, inp.overrides)
        return OrchestratorOutput(answer=body, route="local_user", meta={"intent": intent.dict(), "profile": prof})

    if intent.kind == "base_chat":
        log.info("[PATH] route=base_chat")
        body, prof = local_exec.run_user_base_chat(router, cfg, repo, inp.usr_id, inp.conv_id or 0, inp.query, inp.overrides)
        return OrchestratorOutput(answer=body, route="base_chat", meta={"intent": intent.dict(), "profile": prof})

    # === agent_needed ===
    if not AGENT_ENABLED:
        log.info("[PATH] route=agent_needed_disabled (agent off)")
        return OrchestratorOutput(
            answer="기능에 문제가 있습니다. 잠시 후 다시 시도해주세요!",
            route="agent_needed_disabled",
            meta={"intent": intent.dict()}
        )

    try:
        payload = planner.make_agent_payload(intent, inp.query, inp.usr_id, inp.conv_id, inp.meta.get("session", {}))
        res = agent_client.plan_and_run(payload)

        log.info("[AGENT RES] top_keys=%s data_keys=%s",
                 list(res.keys()),
                 list((res.get("data") or {}).keys()) if isinstance(res.get("data"), dict) else None)

        # 1) RAG 우선: context_snippets / rag blob 등
        rag = _extract_rag_blob(res)
        if rag and (rag.get("matches")):
            usr_name, usr_snm = ("게스트", "")
            if inp.usr_id:
                try:
                    prof = repo.get_user_profile(inp.usr_id)
                    usr_name, usr_snm = prof if prof else ("사용자", "")
                except Exception:
                    pass
            answer = _synthesize_from_rag(router, cfg, inp.query, rag, inp.overrides, usr_name=usr_name, usr_snm=usr_snm)
            return OrchestratorOutput(answer=answer, route="agent_rag", meta={"intent": intent.dict(), "agent_raw": res})

        # 2) 계산형: final_data가 있고, 숫자 결과 키가 실제로 하나 이상 있는 경우에만
        fd = (res or {}).get("final_data") or {}
        numeric_keys = any(k in fd for k in ("user_value", "benchmark", "diff", "ratio"))
        if fd and numeric_keys:
            unit = fd.get("unit", "")
            txt = []
            if "user_value" in fd: txt.append(f"사용자 값: {fd['user_value']}{unit}")
            if "benchmark" in fd:  txt.append(f"비교 기준: {fd['benchmark']}{unit}")
            if "diff" in fd:       txt.append(f"차이: {fd['diff']}{unit}")
            if "ratio" in fd:      txt.append(f"비율: {fd['ratio']:.4f}")
            answer = "\n".join(txt) if txt else "에이전트 결과를 가져왔습니다."
            return OrchestratorOutput(answer=answer, route="agent_calc", meta={"intent": intent.dict(), "agent_raw": res})

        # 3) 에이전트가 문장 자체를 준 경우
        for k in ("final_text", "answer", "text", "message"):
            if isinstance(res.get(k), str) and res[k].strip():
                return OrchestratorOutput(answer=res[k].strip(), route="agent_text", meta={"intent": intent.dict(), "agent_raw": res})
        if isinstance(res.get("data"), dict):
            for k in ("final_text", "answer", "text", "message"):
                v = res["data"].get(k)
                if isinstance(v, str) and v.strip():
                    return OrchestratorOutput(answer=v.strip(), route="agent_text", meta={"intent": intent.dict(), "agent_raw": res})

        # 4) 기타: 안전 폴백
        log.info("[PATH] route=agent (no rag/numeric/text) – default ack")
        return OrchestratorOutput(answer="에이전트 결과를 가져왔습니다.", route="agent", meta={"intent": intent.dict(), "agent_raw": res})

    except Exception:
        # 콜 실패 시에도 동일 메시지로 폴백
        return OrchestratorOutput(
            answer="기능에 문제가 있습니다. 잠시 후 다시 시도해주세요!",
            route="agent_call_failed",
            meta={"intent": intent.dict()}
        )
