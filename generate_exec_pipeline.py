#!/usr/bin/env python3
"""
generate_exec_pipeline.py

Reads 1..N .bat files from a project root, extracts likely Python entrypoints/commands,
optionally merges a user-provided config describing inputs/outputs between steps,
and emits Mermaid diagrams to document the execution pipeline:
- pipeline_overview.mmd (flowchart of .bat -> packages -> stores)
- predict_sequence.mmd (sequence diagram for a chosen .bat, if configured)

USAGE:
  python generate_exec_pipeline.py --root . --bats flaskrun-data.bat flaskrun-predict.bat flaskrun-web.bat \
    --outdir docs/diagrams --config pipeline_config.json
"""
import argparse, json, re
from pathlib import Path
from typing import Dict, List

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
    label = bat_name.replace(".bat","").replace("_"," ").title()
    if "data" in bat_name.lower():
        steps = [
            {"name": "DataHandling", "desc": "CSV/Excel/Crawl", "produces": ["INT"], "consumes": []},
            {"name": "DBHandling", "desc": "Merge/Upload", "produces": ["Oracle"], "consumes": ["INT"]},
        ]
    elif "predict" in bat_name.lower():
        steps = [
            {"name": "TableBuilder*", "desc": "build features & predict", "consumes": ["Oracle","Models"], "produces": ["PredCSV"]},
        ]
    elif "web" in bat_name.lower():
        steps = [
            {"name": "Web API", "desc": "serve charts & admin", "consumes": ["Oracle","Models","PredCSV"], "produces": []},
        ]
    else:
        steps = [{"name": "Task", "desc": "batch job", "consumes": [], "produces": []}]
    return {"label": label, "steps": steps, "commands": commands}

def emit_flowchart(root: Path, outdir: Path, config: Dict, bat_files: List[Path]):
    out = outdir / "pipeline_overview.mmd"
    lines = ["flowchart LR", "  subgraph Batch Entrypoints"]
    for bat in bat_files:
        bid = bat.stem
        lines.append(f"    {bid}[{bat.name}]")
    lines.append("  end\n")

    lines.append("  subgraph Stores")
    for key, val in config.get("stores", {}).items():
        shape = "([["+val+"]])" if key.lower()=="oracle" else f"[{val}]"
        lines.append(f"    {key}{shape}")
    lines.append("  end\n")

    for bat in bat_files:
        bid = bat.stem
        bcfg = config["bats"].get(bat.name) or guess_bat_mapping(bat.name, [])
        lines.append(f"  subgraph {bid}_grp[{bcfg.get('label', bid)}]")
        prev = None
        for idx, step in enumerate(bcfg.get("steps", []), start=1):
            sid = f"{bid}_S{idx}"
            label = f"{step['name']}\\n({step.get('desc','')})".strip()
            lines.append(f"    {sid}[{label}]")
            if prev:
                lines.append(f"    {prev} --> {sid}")
            prev = sid
            for c in step.get("consumes", []):
                lines.append(f"    {c} -.-> {sid}")
            for p in step.get("produces", []):
                lines.append(f"    {sid} --> {p}")
        lines.append("  end\n")
        lines.append(f"  {bid} --> {bid}_S1\n")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out

def emit_sequence(outdir: Path, config: Dict):
    seq_cfg = config.get("sequence") or {}
    if not seq_cfg:
        return None
    out = outdir / "predict_sequence.mmd"
    parts = ["sequenceDiagram", "  autonumber"]
    uniq_parts = []
    for s in seq_cfg.get("actors", []):
        if s not in uniq_parts:
            uniq_parts.append(s)
    for s in uniq_parts:
        parts.append(f"  participant {s}")
    for src, dst, txt in seq_cfg.get("messages", []):
        parts.append(f"  {src}->>{dst}: {txt}")
    out.write_text("\n".join(parts), encoding="utf-8")
    return out

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
            for k,v in user_cfg.items():
                cfg[k] = v
        except Exception as e:
            print(f"[WARN] Failed to parse config: {e}")

    bat_files = []
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
