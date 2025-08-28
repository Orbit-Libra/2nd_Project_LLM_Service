# services/llm_service/orchestrator/graph.py
from typing import List, Dict, Any, Literal, Optional, TypedDict, Tuple
import re
import logging
from langgraph.graph import StateGraph

from . import intent_classifier, local_exec, planner, agent_client
from . import _synthesize_from_rag, _extract_rag_blob
from .intent_classifier import extract_slots_light

log = logging.getLogger("orchestrator.graph")

# =========================
# 타입/스키마
# =========================

Executor = Literal["user_local", "agent_rag", "base_chat", "calculator"]

class Task(TypedDict):
    id: str
    text: str
    intent: Dict[str, Any]
    executor: Executor
    deps: List[str]
    slots: Dict[str, Any]        # owner/entity/year/grade/metric/mode/ref 등

class TaskResult(TypedDict):
    id: str
    executor: Executor
    output: str
    variables: Dict[str, Any]    # year, cps, lps 등

class OrchestratorState(TypedDict):
    query: str
    usr_id: Optional[str]
    conv_id: Optional[int]
    overrides: Dict[str, Any]
    tasks: List[Task]
    results: List[TaskResult]
    errors: List[str]
    router: Any
    cfg: Dict[str, Any]
    repo: Any

# =========================
# 토큰/정규화 유틸
# =========================

def _norm(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^\w가-힣]", "", s)
    return s

_QSEP_RE = re.compile(r"[?？！]\s*")
_AND_TOKENS = ["그리고", "및", "하고", "랑", "이랑", "또", "과", "와"]

_PAGE_NAMES = [
    "학습환경 분석", "발전도 분석", "마이페이지", "내정보", "내 정보",
    "학습환경분석", "발전도분석"
]
_FIELD_TOKENS = ["소속대학", "소속 대학", "자료구입비", "CPS", "대출건수", "LPS", "방문수", "VPS", "예측점수", "점수"]
_EDIT_TOKENS  = ["수정", "변경", "편집", "업데이트", "입력", "저장", "하는 법", "방법"]
_GUIDE_TOKENS = ["어디", "어디서", "경로", "페이지", "버튼", "탭", "어떻게"]

_PAGE_TOK_N  = [_norm(t) for t in _PAGE_NAMES]
_FIELD_TOK_N = [_norm(t) for t in _FIELD_TOKENS]
_EDIT_TOK_N  = [_norm(t) for t in _EDIT_TOKENS]
_GUIDE_TOK_N = [_norm(t) for t in _GUIDE_TOKENS]

def _has_any_normed(text: str, tokens_norm: List[str]) -> bool:
    tn = _norm(text)
    return any(tok in tn for tok in tokens_norm)

# =========================
# 분해기 (세그멘터)
# =========================

def _split_compound(q: str) -> List[str]:
    q = (q or "").strip()
    if not q:
        return []

    # 1) ? 등으로 1차 분해
    parts = [p.strip() for p in _QSEP_RE.split(q) if p.strip()]
    if not parts:
        parts = [q]

    # 2) 연결사로 추가 분해 (페이지/지표가 복수 포함된 경우만)
    out: List[str] = []
    for p in parts:
        pn = _norm(p)
        token_hits = 0
        token_hits += sum(1 for name in _PAGE_TOK_N if name and name in pn)
        token_hits += sum(1 for name in _FIELD_TOK_N if name and name in pn)
        has_and = any(tok in p for tok in _AND_TOKENS) or ("," in p)
        needs_split = has_and and token_hits >= 2

        if not needs_split or len(p) < 14:
            out.append(p); continue

        tmp = p.replace(",", " | ")  # 쉼표도 동등 분할자 취급
        for tok in _AND_TOKENS:
            tmp = re.sub(rf"\s*{re.escape(tok)}\s*", "|", tmp)
        chunks = [c.strip() for c in tmp.split("|") if c.strip()]

        tail = ""
        m_tail = re.search(r"(하는 법|방법|수정|변경|편집|업데이트|입력|저장)\s*$", p)
        if m_tail:
            tail = m_tail.group(1)

        for c in chunks:
            seg = (c if (not tail or tail in c) else f"{c} {tail}").strip()
            out.append(seg)

    return out[:8] if out else [q]

# =========================
# 실행기 선택
# =========================

def _looks_like_guide(text: str) -> bool:
    return _has_any_normed(text, _GUIDE_TOK_N) and _has_any_normed(text, _PAGE_TOK_N)

def _looks_like_edit_guide(text: str) -> bool:
    return _has_any_normed(text, _EDIT_TOK_N)

def _is_affiliation(text: str) -> bool:
    t = _norm(text)
    return ("소속대학" in t) or (("내" in text or "나의" in text) and ("대학" in text or "대학교" in text))

def pick_executor(intent: Dict[str, Any], text: str, usr_id: Optional[str], slots: Dict[str, Any]) -> Executor:
    kind = intent.get("kind")
    reason = intent.get("reason", "")

    if usr_id and _is_affiliation(text) and not _looks_like_guide(text):
        return "user_local"

    if usr_id and kind == "user_local":
        return "user_local"

    if kind == "agent_needed" and ("usage_guide" in reason or "guide" in reason):
        return "agent_rag"

    if _looks_like_guide(text) or _looks_like_edit_guide(text):
        return "agent_rag"

    # 타 대학 데이터 질의 슬랏이면 에이전트(RAG+툴)
    if slots.get("owner") == "other" and slots.get("entity"):
        return "agent_rag"

    if intent.get("wants_calculation"):
        return "calculator"

    if kind == "agent_needed":
        return "agent_rag"

    return "base_chat"

# =========================
# 플래너
# =========================

def plan_tasks(query: str, usr_id: Optional[str]) -> List[Task]:
    reqs = _split_compound(query)
    tasks: List[Task] = []
    for i, r in enumerate(reqs):
        it = intent_classifier.classify(r, usr_id)
        slots = extract_slots_light(r)  # owner/entity/year/grade/metric/mode/ref 등
        ex = pick_executor(it.dict(), r, usr_id, slots)
        tasks.append({"id": f"T{i+1}", "text": r, "intent": it.dict(), "executor": ex, "deps": [], "slots": slots})

    # 간단 의존성: same_year/previous_task → 직전 태스크에 의존
    for idx, t in enumerate(tasks):
        ref = t["slots"].get("ref")
        if ref in ("same_year", "previous_task") and idx > 0:
            t["deps"].append(tasks[idx-1]["id"])

    log.info("[GRAPH] plan: %s", [(t["id"], t["executor"], t["text"], t["slots"]) for t in tasks])
    return tasks

# =========================
# 실행기 구현
# =========================

def run_user_local(ctx) -> TaskResult:
    t: Task = ctx["task"]
    router, cfg, repo, usr_id, overrides = ctx["router"], ctx["cfg"], ctx["repo"], ctx["usr_id"], ctx["overrides"]
    body, _ = local_exec.run_user_local(router, cfg, repo, usr_id, t["text"], overrides)

    vars: Dict[str, Any] = {}
    slots = t.get("slots", {})
    try:
        if slots.get("grade"): vars["grade"] = slots["grade"]
        m_y = re.search(r'(\d{4})\s*년', body)
        if m_y: vars["year"] = int(m_y.group(1))
        m_num = re.search(r'(-?\d[\d,]*)', body)
        if m_num:
            val = float(m_num.group(1).replace(",", ""))
            metric = (slots.get("metric") or "").lower()
            if metric in {"cps","lps","vps","score","budget"}:
                vars[metric] = val
    except Exception:
        pass

    return {"id": t["id"], "executor": "user_local", "output": body, "variables": vars}


def run_agent_rag(ctx) -> TaskResult:
    t: Task = ctx["task"]
    slots = t.get("slots", {})
    is_other_data = (slots.get("owner") == "other" and slots.get("entity") and slots.get("mode") == "data")

    # 1) 타 대학 데이터 질의: Oracle MCP 툴 호출
    if is_other_data:
        year = slots.get("year")
        if not year:
            for r in reversed(ctx["results_so_far"]):
                y = r.get("variables", {}).get("year")
                if y:
                    year = int(y); break

        metric = (slots.get("metric") or "cps").upper() if (slots.get("metric") or "").lower() in {"cps","lps","vps","score","budget"} else slots.get("metric")

        oracle_payload = {
            "tool": "oracle.query_university_metric",
            "args": {
                "university": slots.get("entity"),
                "metric": metric,
                "year": year
            }
        }
        agent_payload = {
            "query": t["text"],
            "hints": ["oracle_univ_data"],
            "conv_id": ctx["conv_id"],
            "wants_calculation": False,
            "slots": t["intent"].get("user_slots", []),
            "tools": [oracle_payload]
        }
        res = agent_client.plan_and_run(agent_payload)

        tool_res = (res.get("tool_result") or res.get("data") or {}).get("oracle.query_university_metric")
        if isinstance(tool_res, dict) and tool_res.get("ok"):
            r = tool_res["result"]
            year_used = r.get("year")
            metric_label = r.get("metric_label") or r.get("metric") or "지표"
            val = r.get("value")
            unit = r.get("unit") or ""
            txt = f"{year_used}년 {r['university']}의 {metric_label} 값은 {val}{unit}입니다."
            vars_out = {"year": year_used}
            mkey = (slots.get("metric") or "").lower()
            if mkey in {"cps","lps","vps","score","budget"}:
                vars_out[mkey] = val
            return {"id": t["id"], "executor": "agent_rag", "output": txt, "variables": vars_out}

        log.info("[AGENT RAG] oracle tool failed or not present, fallback to RAG synthesis.")

    # 2) 일반 RAG 합성 경로
    payload = {
        "query": t["text"],
        "hints": ["rag_service_guide" if slots.get("mode") == "guide" else "rag_general"],
        "conv_id": ctx["conv_id"],
        "wants_calculation": False,
        "slots": t["intent"].get("user_slots", [])
    }
    res = agent_client.plan_and_run(payload)

    rag = _extract_rag_blob(res) or {}
    if "matches" not in rag:
        for k in ("final_text", "answer", "text", "message"):
            v = res.get(k) or (res.get("data", {}) if isinstance(res.get("data"), dict) else {}).get(k)
            if isinstance(v, str) and v.strip():
                return {"id": t["id"], "executor": "agent_rag", "output": v.strip(), "variables": {}}

    usr_name, usr_snm = ("게스트", "")
    if ctx["usr_id"]:
        try:
            prof = ctx["repo"].get_user_profile(ctx["usr_id"])
            usr_name, usr_snm = prof if prof else ("사용자", "")
        except Exception:
            pass

    answer = _synthesize_from_rag(ctx["router"], ctx["cfg"], t["text"], rag, ctx["overrides"],
                                  usr_name=usr_name, usr_snm=usr_snm)
    return {"id": t["id"], "executor": "agent_rag", "output": answer, "variables": {}}


def run_base_chat(ctx) -> TaskResult:
    t: Task = ctx["task"]
    if ctx["usr_id"]:
        body, _ = local_exec.run_user_base_chat(ctx["router"], ctx["cfg"], ctx["repo"],
                                                ctx["usr_id"], ctx["conv_id"] or 0,
                                                t["text"], ctx["overrides"])
    else:
        body = local_exec.run_guest_base_chat(ctx["router"], ctx["cfg"], t["text"], ctx["overrides"])
    return {"id": t["id"], "executor": "base_chat", "output": body, "variables": {}}


def run_calculator(ctx) -> TaskResult:
    t: Task = ctx["task"]
    env: Dict[str, float] = {}
    for r in ctx["results_so_far"]:
        for k, v in r.get("variables", {}).items():
            if isinstance(v, (int, float)):
                env[f"{r['id']}_{k}"] = float(v)

    expr = t["text"].replace("퍼센트", "/100")
    expr = re.sub(r"[^\d\+\-\*\/\.\(\)\s]", " ", expr)

    try:
        val = eval(expr, {"__builtins__": {}}, env)  # 실제 서비스에선 안전한 평가기로 교체 권장
        out = f"{val}"
        variables = {"value": float(val)}
    except Exception:
        out, variables = "계산에 필요한 값이 부족합니다.", {}

    return {"id": t["id"], "executor": "calculator", "output": out, "variables": variables}

# =========================
# LangGraph 정의/엔트리
# =========================

def build_graph():
    g = StateGraph(OrchestratorState)

    def n_plan(s: OrchestratorState) -> OrchestratorState:
        tasks = plan_tasks(s["query"], s["usr_id"])
        return {**s, "tasks": tasks}

    g.add_node("plan", n_plan)

    def n_execute(s: OrchestratorState) -> OrchestratorState:
        results: List[TaskResult] = list(s["results"])
        for t in s["tasks"]:
            ctx = {
                "task": t,
                "router": s["router"], "cfg": s["cfg"], "repo": s["repo"],
                "usr_id": s["usr_id"], "conv_id": s["conv_id"],
                "overrides": s["overrides"], "results_so_far": results
            }
            try:
                ex = t["executor"]
                if ex == "user_local":
                    res = run_user_local(ctx)
                elif ex == "agent_rag":
                    res = run_agent_rag(ctx)
                elif ex == "calculator":
                    res = run_calculator(ctx)
                else:
                    res = run_base_chat(ctx)
                results.append(res)
            except Exception as e:
                log.exception("task execute error: %s", e)
                results.append({"id": t["id"], "executor": t["executor"],
                                "output": f"요청 처리 중 오류가 발생했습니다: {e}", "variables": {}})
        return {**s, "results": results}

    g.add_node("execute", n_execute)
    g.add_edge("plan", "execute")

    def n_compose(s: OrchestratorState) -> OrchestratorState:
        chunks = [r["output"].strip() for r in s["results"] if r.get("output")]
        chunks = [c for c in chunks if c]

        if not chunks:
            final = "답변을 생성할 수 없습니다."
        elif len(chunks) == 1:
            final = chunks[0]
        else:
            final = "\n".join([f"- {c}" for c in chunks])

        return {**s, "final_answer": final}

    g.add_node("compose", n_compose)
    g.add_edge("execute", "compose")

    g.set_entry_point("plan")
    g.set_finish_point("compose")
    return g


def run_orchestrator_graph(router, cfg, repo, inp) -> Tuple[str, List[Task], List[TaskResult]]:
    graph = build_graph()
    state: OrchestratorState = {
        "query": inp.query,
        "usr_id": inp.usr_id,
        "conv_id": inp.conv_id,
        "overrides": inp.overrides or {},
        "tasks": [],
        "results": [],
        "errors": [],
        "router": router,
        "cfg": cfg,
        "repo": repo,
    }
    # 1단계: 먼저 플랜만 구해서 토큰 스케일링 파라미터 계산
    tasks = plan_tasks(state["query"], state["usr_id"])
    agent_heavy = any(t["executor"] == "agent_rag" for t in tasks)
    scaled_ov = local_exec.with_scaled_tokens(cfg, inp.overrides or {}, task_count=len(tasks), agent_heavy=agent_heavy)
    # 실행 단계에 스케일된 overrides 주입
    state["overrides"] = scaled_ov
    state["tasks"] = tasks
    # 이제 그래프 실행 (execute→compose)
    out = graph.invoke(state)
    return out["final_answer"], out["tasks"], out["results"]
