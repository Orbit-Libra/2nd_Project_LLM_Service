#!/usr/bin/env python3
"""
generate_exec_pipeline.py

Reads 1..N .bat files from a project root, extracts likely Python entrypoints/commands,
optionally merges a user-provided config describing inputs/outputs between steps,
and emits Mermaid diagrams to document the execution pipeline:
- pipeline_overview.mmd (flowchart of .bat -> packages -> stores)
- predict_sequence.mmd (sequence diagram for a chosen .bat, if configured)

USAGE:
  python generate_exec_pipeline.py --root . --bats setup-pipeline.bat flaskrun-data.bat flaskrun-predict.bat flaskrun-web.bat \
    --outdir docs/diagrams --config docs/diagrams/pipeline_config.json
"""
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

# ---------- Mermaid-safe helpers ----------
SAFE_ID_RE = re.compile(r'[^A-Za-z0-9_]')
START_ALPHA_RE = re.compile(r'^[A-Za-z]')

def safe_id(s: str) -> str:
    """Normalize any string into a Mermaid-safe identifier: [A-Za-z][A-Za-z0-9_]*"""
    s = SAFE_ID_RE.sub('_', s)
    if not START_ALPHA_RE.match(s[:1] or ''):
        s = 'N_' + s
    return s

def box(label: str) -> str:
    """Return a Mermaid box node with a quoted label."""
    # Always quote to avoid * / : ( etc. being parsed as syntax/markdown
    return f'["{label}"]'

# ---------- Batch parsing ----------
PY_CMD_RE = re.compile(r'(^|[ &])(?P<cmd>python|py|flask|gunicorn)\b.*', re.IGNORECASE)

DEFAULT_STORES = {
    "Oracle": "Oracle DB",
    "Models": "services/ml_service/_Models/*.pkl",
    "PredCSV": "outputs/predictions/*.csv",
    "INT": "data/intermediate/*",
    "RAW": "data/raw/*",
}

DEFAULT_CONFIG = {
    "stores": DEFAULT_STORES,
    "bats": {},
    "stores_detail": {},
    "sequence": {}
}

def read_bat_commands(bat_path: Path) -> List[str]:
    try:
        lines = bat_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    cmds = []
    for ln in lines:
        m = PY_CMD_RE.search(ln.strip())
        if m:
            cmds.append(ln.strip())
    return cmds

def guess_bat_mapping(bat_name: str, commands: List[str]) -> Dict:
    label = bat_name
    name_l = bat_name.lower()
    if "data" in name_l:
        steps = [
            {"name": "DataHandling", "desc": "CSV/Excel/Crawl", "produces": ["INT"], "consumes": []},
            {"name": "DBHandling", "desc": "Merge/Upload", "produces": ["Oracle"], "consumes": ["INT"]},
        ]
    elif "predict" in name_l:
        steps = [
            {"name": "TableBuilder*", "desc": "build features & predict", "consumes": ["Oracle","Models"], "produces": ["PredCSV"]},
        ]
    elif "web" in name_l:
        steps = [
            {"name": "Web API", "desc": "serve charts & admin", "consumes": ["Oracle","Models","PredCSV"], "produces": []},
        ]
    else:
        steps = [{"name": "Task", "desc": "batch job", "consumes": [], "produces": []}]
    return {"label": label, "steps": steps, "commands": commands}

# ---------- Emit flowchart ----------
def emit_flowchart(root: Path, outdir: Path, config: Dict, bat_files: List[Path]):
    out = outdir / "pipeline_overview.mmd"
    lines: List[str] = []
    lines.append("flowchart LR")

    # Batch Entrypoints
    lines.append("  subgraph Batch_Entrypoints")
    batch_ids = []
    for bat in bat_files:
        bid = safe_id(bat.stem)
        batch_ids.append(bid)
        lines.append(f"    {bid}{box(bat.name)}")
    lines.append("  end\n")

    # Stores
    lines.append("  subgraph Stores")
    store_id_map: Dict[str, str] = {}
    for key, val in config.get("stores", {}).items():
        sid = safe_id(key)
        store_id_map[key] = sid
        # 단순 박스가 가장 호환성이 좋음
        lines.append(f"    {sid}{box(val)}")
    lines.append("  end\n")

    # Per-batch steps
    for bat in bat_files:
        bid = safe_id(bat.stem)
        bcfg = config["bats"].get(bat.name) or guess_bat_mapping(bat.name, [])
        grp_id = f"{bid}_grp"
        grp_label = bcfg.get("label", bat.name)
        lines.append(f"  subgraph {grp_id}{box(grp_label)}")
        prev_sid = None
        for idx, step in enumerate(bcfg.get("steps", []), start=1):
            sid = safe_id(f"{bid}_S{idx}")
            label = f"{step.get('name','Step')}\\n({step.get('desc','')})".strip()
            lines.append(f"    {sid}{box(label)}")
            if prev_sid:
                lines.append(f"    {prev_sid} --> {sid}")
            prev_sid = sid
            # consumes / produces
            for c in step.get("consumes", []):
                c_id = store_id_map.get(c, safe_id(c))
                lines.append(f"    {c_id} -.-> {sid}")
            for p in step.get("produces", []):
                p_id = store_id_map.get(p, safe_id(p))
                lines.append(f"    {sid} --> {p_id}")
        lines.append("  end\n")
        # Entrypoint to first step
        lines.append(f"  {bid} --> {safe_id(f'{bid}_S1')}\n")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out

# ---------- Emit sequence ----------
def emit_sequence(outdir: Path, config: Dict):
    seq_cfg = config.get("sequence") or {}
    if not seq_cfg:
        return None
    out = outdir / "predict_sequence.mmd"

    # Map actor labels to safe ids
    actor_labels: List[str] = list(dict.fromkeys(seq_cfg.get("actors", [])))  # preserve order, unique
    actor_ids = {label: safe_id(label) for label in actor_labels}

    parts: List[str] = []
    parts.append("sequenceDiagram")
    parts.append("  autonumber")
    for label in actor_labels:
        parts.append(f'  participant {actor_ids[label]} as "{label}"')

    for src, dst, txt in seq_cfg.get("messages", []):
        sid = actor_ids.get(src, safe_id(src))
        did = actor_ids.get(dst, safe_id(dst))
        parts.append(f'  {sid}->>{did}: {txt}')

    out.write_text("\n".join(parts), encoding="utf-8")
    return out

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--bats", nargs="+", required=True, help="List of .bat files to parse from --root")
    ap.add_argument("--config", type=Path, default=None, help="Optional JSON config to refine stores/steps/sequence")
    ap.add_argument("--outdir", type=Path, default=Path("docs/diagrams"))
    args = ap.parse_args()

    root = args.root.resolve()
    outdir = (root / args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    cfg = DEFAULT_CONFIG.copy()
    if args.config and args.config.exists():
        try:
            user_cfg = json.loads(args.config.read_text(encoding="utf-8"))
            # shallow merge
            for k, v in user_cfg.items():
                cfg[k] = v
        except Exception as e:
            print(f"[WARN] Failed to parse config: {e}")

    bat_files: List[Path] = []
    for b in args.bats:
        p = (root / b).resolve()
        if not p.exists():
            print(f"[WARN] .bat not found: {p}")
        else:
            bat_files.append(p)
            commands = read_bat_commands(p)
            if b not in cfg["bats"]:
                cfg["bats"][Path(b).name] = guess_bat_mapping(Path(b).name, commands)
            else:
                cfg["bats"][Path(b).name]["commands"] = commands

    fc_path = emit_flowchart(root, outdir, cfg, bat_files)
    sd_path = emit_sequence(outdir, cfg)

    if not args.config:
        skel = outdir / "pipeline_config.skeleton.json"
        skel.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[INFO] Wrote config skeleton: {skel}")
    print(f"[OK] Flowchart: {fc_path}")
    if sd_path:
        print(f"[OK] Sequence: {sd_path}")

if __name__ == "__main__":
    main()
