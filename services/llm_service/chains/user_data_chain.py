# services/llm_service/chains/user_data_chain.py
import os
import re
import json
import logging
from typing import Any, Dict, List, Tuple, Optional
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from services.llm_service.db import llm_repository_cx as repo
from services.llm_service.model.prompts import render_messages

log = logging.getLogger("user_data_chain")

# =========================
# 유틸: alias 정규화/접기
# =========================

_FIELDS = ("year", "CPS", "LPS", "VPS", "score")
_SEP = re.compile(r"[.\s_\-/:]+")

_COL_NORM = re.compile(r'[^A-Za-z0-9_]+')
def _norm_col(name: str) -> str:
    return _COL_NORM.sub('', (name or '').strip()).upper()

def _normalize_alias_keys(row_aliases: Dict[str, Any]) -> Dict[str, Any]:
    """
    row_aliases(dict) -> 표준형 키로 통일한 dict 반환.
    허용 예: y1.year, y1_year, Y1.YEAR, y2-lps, y3 vps, y4/SCORE ...
    """
    norm: Dict[str, Any] = {}
    for raw_k, v in (row_aliases or {}).items():
        # 값이 None이면 제외 (정답 산출에 도움되지 않음)
        if v is None:
            continue

        k = str(raw_k).strip()
        if k in ("name", "university"):
            norm[k] = v
            continue

        toks = [t for t in _SEP.split(k) if t]
        toks_l = [t.lower() for t in toks]

        # y{n}
        year_idx = 0
        for t in toks_l:
            m = re.fullmatch(r"y([1-4])", t)
            if m:
                year_idx = int(m.group(1))
                break
        if not year_idx:
            continue

        # field
        fld = None
        for t in toks_l:
            if t in ("year", "yr"):
                fld = "year"; break
            if t in ("cps",):
                fld = "CPS"; break
            if t in ("lps", "loan", "loans"):
                fld = "LPS"; break
            if t in ("vps", "visit", "visits"):
                fld = "VPS"; break
            if t in ("score", "scr", "scr_est", "scr-est"):
                fld = "score"; break

        if fld and fld in _FIELDS:
            norm[f"y{year_idx}.{fld}"] = v
    return norm

def _fold_from_norm(norm: Dict[str, Any]) -> Dict[str, Any]:
    """
    정규화된 dict -> 내부 표준 구조 {name, university, y1:{...}, ...}
    """
    out: Dict[str, Any] = {
        "name": norm.get("name"),
        "university": norm.get("university"),
    }
    for i in range(1, 5):
        out[f"y{i}"] = {
            "year":  norm.get(f"y{i}.year"),
            "CPS":   norm.get(f"y{i}.CPS"),
            "LPS":   norm.get(f"y{i}.LPS"),
            "VPS":   norm.get(f"y{i}.VPS"),
            "score": norm.get(f"y{i}.score"),
        }
    return out

def _has_any_year_payload(data: Dict[str, Any]) -> bool:
    """y1~y4 중 하나라도 year/CPS/LPS/VPS/score 값이 있으면 True"""
    for i in range(1, 5):
        y = (data or {}).get(f"y{i}") or {}
        if any(y.get(k) not in (None, "") for k in ("year", "CPS", "LPS", "VPS", "score")):
            return True
    return False

# =========================
# 데이터 로딩
# =========================

# 숫자로 시작하는 컬럼을 안전하게 감싸는 헬퍼
def _maybe_quote(c: str) -> str:
    return f'"{c}"' if c and c[0].isdigit() else c

def _fetch_user_data_via_schema_local(usr_id: str, schema_path: Optional[str]) -> Dict[str, Any]:
    """
    user_schema.json을 직접 파싱해 SELECT를 만들고 실행한다.
    반환: {name, university, y1..y4:{year,CPS,LPS,VPS,score}}
    """
    try:
        if not schema_path or not os.path.exists(schema_path):
            raise FileNotFoundError(f"user schema not found: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        tables = schema.get("tables", [])
        t_user = next((t for t in tables if t.get("name") == "USER_DATA"), None)
        if not t_user:
            raise ValueError("USER_DATA table not found in schema")

        id_col = t_user.get("id_column") or "USR_ID"
        cols = t_user.get("columns") or {}

        # SELECT 컬럼 목록과 alias 매핑 준비
        select_cols: List[str] = []
        alias_map: Dict[str, str] = {}  # 정규화된 DB 컬럼명 -> alias(y2.LPS 등)
        for db_col, meta in cols.items():
            select_cols.append(db_col)
            alias = (meta or {}).get("alias")
            if alias:
                alias_map[_norm_col(db_col)] = alias  # ✅ 정규화해서 저장

        select_cols_uniq = list(dict.fromkeys(select_cols))
        # ✅ 숫자로 시작하는 컬럼은 더블쿼트로 감싸서 Oracle이 이름을 망가뜨리지 않게
        select_for_sql = [_maybe_quote(c) for c in select_cols_uniq]

        sql = f"SELECT {', '.join(select_for_sql)} FROM USER_DATA WHERE {id_col} = :usr_id"
        params = {"usr_id": usr_id}

        # ✅ description을 믿지 말고 tuple로 받고, 우리가 알고 있는 원래 컬럼명으로 dict 구성
        row_dict: Optional[Dict[str, Any]] = None
        if hasattr(repo, "fetch_one"):
            row = repo.fetch_one(sql, params)
            if row:
                # 키는 정규화된 원래 컬럼명 (예: 1ST_YR → 1ST_YR)
                row_dict = {_norm_col(select_cols_uniq[i]): row[i] for i in range(len(select_cols_uniq))}
        else:
            # 최후의 보루 (여전히 description 문제 있을 수 있음)
            row_dict = repo.fetch_one_dict(sql, params) if hasattr(repo, "fetch_one_dict") else None

        log.info("[UDC] via_schema sql=%s", sql)
        if not row_dict:
            log.info("[UDC] via_schema: no row")
            return {}

        # 디버그
        log.info("[UDC] via_schema row_dict keys=%s", list(row_dict.keys())[:40])
        probe_keys = [
            "USR_NAME","USR_SNM",
            "1ST_USR_LPS","2ND_USR_LPS","3RD_USR_LPS","4TH_USR_LPS",
            "1ST_YR","2ND_YR","3RD_YR","4TH_YR",
            "SCR_EST_1ST","SCR_EST_2ND","SCR_EST_3RD","SCR_EST_4TH"
        ]
        log.info("[UDC] via_schema row_dict probe=%s",
                 {k: row_dict.get(k) for k in probe_keys})

        # alias 키로 재구성
        row_aliases: Dict[str, Any] = {}
        for norm_db_col, alias in alias_map.items():
            if norm_db_col in row_dict:
                row_aliases[alias] = row_dict[norm_db_col]

        # 프로필 보정
        if "name" not in row_aliases and "USR_NAME" in row_dict:
            row_aliases["name"] = row_dict["USR_NAME"]
        if "university" not in row_aliases and "USR_SNM" in row_dict:
            row_aliases["university"] = row_dict["USR_SNM"]

        log.info("[UDC] via_schema alias_keys=%s", sorted(list(row_aliases.keys()))[:40])

        # 정규화/접기
        norm = _normalize_alias_keys(row_aliases)
        folded = _fold_from_norm(norm)

        log.info("[UDC] via_schema folded_y1=%s", folded.get("y1"))
        log.info("[UDC] via_schema folded_y2=%s", folded.get("y2"))
        log.info("[UDC] via_schema folded_y3=%s", folded.get("y3"))
        log.info("[UDC] via_schema folded_y4=%s", folded.get("y4"))

        return folded

    except Exception as e:
        log.warning("[UDC] via_schema error: %s", e)
        return {}

def _fetch_user_data_direct(usr_id: str) -> Dict[str, Any]:
    """
    스키마 경로 실패 시 직접 SELECT로 조회.
    """
    cols = [
        "USR_NAME", "USR_SNM",
        "1ST_YR", "1ST_USR_CPS", "1ST_USR_LPS", "1ST_USR_VPS", "SCR_EST_1ST",
        "2ND_YR", "2ND_USR_CPS", "2ND_USR_LPS", "2ND_USR_VPS", "SCR_EST_2ND",
        "3RD_YR", "3RD_USR_CPS", "3RD_USR_LPS", "3RD_USR_VPS", "SCR_EST_3RD",
        "4TH_YR", "4TH_USR_CPS", "4TH_USR_LPS", "4TH_USR_VPS", "SCR_EST_4TH",
    ]
    # ✅ 숫자 시작 컬럼은 더블쿼트
    sql = f"SELECT {', '.join([_maybe_quote(c) for c in cols])} FROM USER_DATA WHERE USR_ID = :usr_id"
    try:
        d: Optional[Dict[str, Any]] = None
        if hasattr(repo, "fetch_one"):
            row = repo.fetch_one(sql, {"usr_id": usr_id})
            if row:
                d = {c.upper(): row[i] for i, c in enumerate(cols)}
        elif hasattr(repo, "fetch_one_dict"):
            d = repo.fetch_one_dict(sql, {"usr_id": usr_id})
            if d:
                d = {k.upper(): v for k, v in d.items()}

        if not d:
            return {}

        # 프리뷰
        log.info("[UDC] direct preview: "
                 "1ST_YR=%r 2ND_YR=%r 3RD_YR=%r 4TH_YR=%r | "
                 "2ND_USR_LPS=%r 3RD_USR_LPS=%r 4TH_USR_LPS=%r",
                 d.get("1ST_YR"), d.get("2ND_YR"), d.get("3RD_YR"), d.get("4TH_YR"),
                 d.get("2ND_USR_LPS"), d.get("3RD_USR_LPS"), d.get("4TH_USR_LPS"))

        out = {
            "name": d.get("USR_NAME"),
            "university": d.get("USR_SNM"),
            "y1": {"year": d.get("1ST_YR"), "CPS": d.get("1ST_USR_CPS"), "LPS": d.get("1ST_USR_LPS"),
                   "VPS": d.get("1ST_USR_VPS"), "score": d.get("SCR_EST_1ST")},
            "y2": {"year": d.get("2ND_YR"), "CPS": d.get("2ND_USR_CPS"), "LPS": d.get("2ND_USR_LPS"),
                   "VPS": d.get("2ND_USR_VPS"), "score": d.get("SCR_EST_2ND")},
            "y3": {"year": d.get("3RD_YR"), "CPS": d.get("3RD_USR_CPS"), "LPS": d.get("3RD_USR_LPS"),
                   "VPS": d.get("3RD_USR_VPS"), "score": d.get("SCR_EST_3RD")},
            "y4": {"year": d.get("4TH_YR"), "CPS": d.get("4TH_USR_CPS"), "LPS": d.get("4TH_USR_LPS"),
                   "VPS": d.get("4TH_USR_VPS"), "score": d.get("SCR_EST_4TH")},
        }
        return out
    except Exception as e:
        log.warning("[UDC] direct error: %s", e)
        return {}

def load_full_user_data(usr_id: str, prof_fallback: Optional[Tuple[str, str]], cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    1) 스키마 경유 조회(로컬 파서)
    2) 학년 데이터 없으면 직접 SELECT fallback
    3) 그래도 없으면 프로필만
    """
    schema_path = (cfg or {}).get("user_schema_path") or os.getenv("USER_SCHEMA_CONFIG")

    via = _fetch_user_data_via_schema_local(usr_id, schema_path)
    if via and _has_any_year_payload(via):
        return via

    direct = _fetch_user_data_direct(usr_id)
    if direct and _has_any_year_payload(direct):
        log.info("[UDC] fallback: direct select used.")
        return direct

    name, snm = (prof_fallback or ("사용자", "미상"))
    log.info("[UDC] no year payload found. using profile only.")
    return {"name": name, "university": snm}

# =========================
# 분류/파싱/직답
# =========================

def analyze_question_type(message: str) -> str:
    m = (message or "").strip()
    if ("연도" in m) or ("년도" in m) or ("언제" in m) or ("몇 년" in m) or ("몇년" in m):
        return "year_of_study"
    if any(k in m for k in ["자료구입", "자료 구입", "구입비", "구입 비용", "예산", "신청", "CPS", "cps"]):
        return "material_cost"
    if any(k in m for k in ["대출건수", "대출 건수", "대출", "책 대출", "LPS", "lps"]):
        return "book_loans"
    if any(k in m for k in ["도서관", "방문", "출입", "VPS", "vps"]):
        return "library_visits"
    if any(k in m for k in ["예측점수", "예측 점수", "점수", "스코어", "score", "SCR_EST", "scr_est"]):
        return "score"
    if any(f"{i}학년" in m or f"{i} 학년" in m for i in range(1, 5)):
        return "academic_year"
    if any(k in m for k in ["비교", "더", "많이", "적게", "차이"]):
        return "comparison"
    if any(k in m for k in ["총", "전체", "모두", "합계"]):
        return "total"
    return "general"

def extract_year_number(message: str) -> int:
    m = (message or "")
    # 불필요 기호 제거
    m = re.sub(r"[^\w\s가-힣]", " ", m)
    m = re.sub(r"\s+", " ", m)
    m1 = re.search(r"([1-4])\s*학년", m)
    if m1:
        return int(m1.group(1))
    m2 = re.search(r"\b([1-4])(?:st|nd|rd|th)\b", m, flags=re.I)
    if m2:
        return int(m2.group(1))
    mapping = {"첫": 1, "둘": 2, "두": 2, "셋": 3, "세": 3, "넷": 4}
    for k, v in mapping.items():
        if k in m and "학년" in m:
            return v
    return 0

def _pick_relevant(user_data: Dict[str, Any], qtype: str, message: str) -> Dict[str, Any]:
    if not user_data:
        return {}
    relevant = {"name": user_data.get("name"), "university": user_data.get("university")}
    target = extract_year_number(message) if qtype in ("academic_year","year_of_study","score","material_cost","book_loans","library_visits") else 0

    def pick(idx: int) -> Dict[str, Any]:
        y = user_data.get(f"y{idx}", {}) or {}
        return {"year": y.get("year"), "CPS": y.get("CPS"), "LPS": y.get("LPS"), "VPS": y.get("VPS"), "score": y.get("score")}

    if target:
        relevant["target_year"] = target
        relevant[f"y{target}"] = pick(target)
    else:
        for i in range(1, 5):
            relevant[f"y{i}"] = pick(i)

    # 프루닝
    def prune(d: Dict[str, Any], keep: List[str]) -> Dict[str, Any]:
        return {k: d.get(k) for k in keep if k in d}

    if qtype == "library_visits":
        for i in range(1,5):
            if f"y{i}" in relevant: relevant[f"y{i}"] = prune(relevant[f"y{i}"], ["year","VPS"])
    elif qtype == "book_loans":
        for i in range(1,5):
            if f"y{i}" in relevant: relevant[f"y{i}"] = prune(relevant[f"y{i}"], ["year","LPS"])
    elif qtype == "material_cost":
        for i in range(1,5):
            if f"y{i}" in relevant: relevant[f"y{i}"] = prune(relevant[f"y{i}"], ["year","CPS"])
    elif qtype == "score":
        for i in range(1,5):
            if f"y{i}" in relevant: relevant[f"y{i}"] = prune(relevant[f"y{i}"], ["year","score"])

    return relevant

def _format_context(data: Dict[str, Any]) -> str:
    if not data:
        return ""
    name = data.get("name", "사용자"); uni = data.get("university", "미상")
    lines: List[str] = []
    lines += [
        "[사용자 데이터 사전]",
        "- CPS: 자료구입비(원)",
        "- LPS: 도서 대출 건수(건)",
        "- VPS: 도서관 방문 횟수(회)",
        "- score: 학년별 예측점수",
        "",
        f"[프로필] 이름={name}, 소속={uni}"
    ]
    def row(i: int, y: Dict[str, Any]) -> str:
        if not y: return ""
        parts = [f"{i}학년" + (f"({y.get('year')}년)" if y.get('year') is not None else "")]
        for k in ["CPS","LPS","VPS","score"]:
            if y.get(k) is not None: parts.append(f"{k}={y.get(k)}")
        return " / ".join(parts)
    tgt = data.get("target_year")
    if tgt:
        s = row(tgt, data.get(f"y{tgt}", {}));  s and lines.append(s)
    for i in range(1,5):
        if tgt and i == tgt: continue
        s = row(i, data.get(f"y{i}", {})); s and lines.append(s)
    return "\n".join(lines)

def _direct_answer(relevant: Dict[str, Any], qtype: str, message: str) -> Optional[str]:
    """
    DB 값이 곧 정답인 케이스는 여기서 즉답.
    """
    tgt = extract_year_number(message)
    def get(idx: int, key: str):
        y = relevant.get(f"y{idx}", {}) or {}
        return y.get(key)

    if qtype == "year_of_study" and tgt:
        val = get(tgt, "year")
        return f"{tgt}학년을 이수한 연도는 {val}년입니다!" if val not in (None, "") else "기록이 없습니다."

    if qtype == "material_cost" and tgt:
        val = get(tgt, "CPS")
        return f"{tgt}학년의 자료구입비는 {val}원입니다!" if val not in (None, "") else "기록이 없습니다."

    if qtype == "book_loans" and tgt:
        val = get(tgt, "LPS")
        return f"{tgt}학년의 도서 대출 건수는 {val}건입니다!" if val not in (None, "") else "기록이 없습니다."

    if qtype == "score" and tgt:
        val = get(tgt, "score")
        return f"{tgt}학년의 예측점수는 {val}입니다!" if val not in (None, "") else "기록이 없습니다."

    return None  # 나머지는 LLM

# =========================
# 체인
# =========================

def build_user_data_chain(backend_generate_fn, cfg: Dict[str, Any]):
    def enrich_with_user_data(inp: Dict[str, Any]) -> Dict[str, Any]:
        usr_id = inp.get("usr_id")
        message = inp.get("message", "")
        if not usr_id:
            inp["has_user_data"] = False
            inp["question_type"] = "general"
            inp["_relevant"] = {}
            return inp

        # 프로필 (이름/소속)
        try:
            prof = repo.get_user_profile(usr_id)
        except Exception:
            prof = None

        try:
            full = load_full_user_data(usr_id, prof, cfg)
            qtype = analyze_question_type(message)
            rel = _pick_relevant(full, qtype, message)
            ctx  = _format_context(rel)

            inp["question_type"] = qtype
            inp["user_context"]  = ctx
            inp["has_user_data"] = bool(ctx.strip())
            inp["_relevant"]     = rel
        except Exception as e:
            log.warning("[UDC] enrich error: %s", e)
            inp["question_type"] = "general"
            inp["user_context"]  = ""
            inp["has_user_data"] = False
            inp["_relevant"]     = {}
        return inp

    def maybe_answer_directly(inp: Dict[str, Any]) -> Dict[str, Any]:
        ans = _direct_answer(inp.get("_relevant", {}), inp.get("question_type",""), inp.get("message",""))
        if ans is not None:
            inp["answer"] = ans
            inp["_done"] = True
        else:
            inp["_done"] = False
        return inp

    def build_messages(inp: Dict[str, Any]) -> Dict[str, Any]:
        if inp.get("_done"):
            return inp

        prompts_cfg = cfg.get("prompts", {}) or {}
        roles = prompts_cfg.get("roles", []) or []
        variables = prompts_cfg.get("variables", {}) or {}
        merged_vars = {
            **variables,
            "user_name": inp.get("user_name", ""),
            "salutation_prefix": inp.get("salutation_prefix", ""),
            "user_affiliation": inp.get("user_affiliation", ""),
        }

        base = render_messages(roles, merged_vars)
        messages: List[Dict[str, str]] = list(base)

        if inp.get("has_user_data") and inp.get("user_context"):
            messages.append({"role": "system", "content":
                "[STRICT DATA ANSWER]\n"
                "아래 사용자 데이터만을 근거로 답하라. 없는 값은 '기록이 없습니다'라고 답하라. 임의 추론 금지."
            })
            messages.append({"role": "system", "content": inp["user_context"]})
            # 가이드 간단화 (LLM 사용 경감)
            qtype = inp.get("question_type","")
            guide_map = {
                "year_of_study": "질문은 특정 학년의 이수 연도입니다. year 값만 답하십시오.",
                "material_cost": "질문은 자료구입비(CPS)입니다. 원 단위 숫자만 답하십시오.",
                "book_loans":   "질문은 도서 대출(LPS)입니다. 건 단위 숫자만 답하십시오.",
                "library_visits":"질문은 도서관 방문(VPS)입니다. 회 단위 숫자만 답하십시오.",
                "score":        "질문은 학년별 예측점수(score)입니다. 숫자만 답하십시오.",
            }
            if qtype in guide_map:
                messages.append({"role": "system", "content": guide_map[qtype]})

        messages.append({"role": "user", "content": inp.get("message","")})
        inp["messages"] = messages
        return inp

    def call_backend(inp: Dict[str, Any]) -> Dict[str, Any]:
        if inp.get("_done"):
            return inp
        try:
            overrides = inp.get("overrides", {}) or {}
            text = backend_generate_fn(messages=inp["messages"], overrides=overrides)
            inp["answer"] = text
        except Exception as e:
            inp["answer"] = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
        return inp

    chain = (
        RunnablePassthrough()
        | RunnableLambda(enrich_with_user_data)
        | RunnableLambda(maybe_answer_directly)
        | RunnableLambda(build_messages)
        | RunnableLambda(call_backend)
    )
    return chain
