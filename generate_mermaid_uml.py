#!/usr/bin/env python3
"""
generate_mermaid_uml.py (final — short IDs, import-aware edges, alias-free)

- Mermaid ID: <ClassName>__<6-hex>  (짧고 유니크, alias 미사용)
- 클래스 블록만 사용: class <ID> { ... }  → 파서 호환성↑
- 모듈/네임스페이스는 루트 상대 경로를 축약하여 ID로 사용(길이 단축)
- 의존(uses/has) 탐지 강화:
  * 프로젝트 전체 모듈→클래스 인덱스
  * import / from-import / alias 해석 (alias -> module, symbol -> module)
  * 호출 해석: Class(), alias.Class(), alias.sub.module.Class()
  * 간접 할당: x = Class(); self.y = x → has
  * 타입힌트 AnnAssign: self.y: Class → has
  * 클래스 본문 텍스트에 대한 정규식 보조 스캔

USAGE:
  python generate_mermaid_uml.py /path/to/project
  # 기본 출력: docs/diagrams/uml_class_diagram.mmd
"""
import ast
import argparse
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

DEFAULT_EXCLUDES = {".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".git"}

# ---------------- helpers ----------------
def should_skip(path: Path, excludes: Set[str]) -> bool:
    return any(part in excludes for part in path.parts)

def iter_py_files(root: Path, excludes: Set[str]):
    for p in root.rglob("*.py"):
        if should_skip(p, excludes):
            continue
        yield p

SAFE_ID_RE = re.compile(r'[^A-Za-z0-9_]')
def sanitize_mermaid_id(s: str) -> str:
    s = SAFE_ID_RE.sub("_", s)
    if not s or not s[0].isalpha():
        s = "N_" + s
    return s

def short_namespace_id(module_rel: str, max_parts: int = 3) -> str:
    """
    긴 모듈 경로를 짧게: 마지막 max_parts만 취해서 namespace ID 생성
    """
    parts = module_rel.split(".")
    tail = parts[-max_parts:] if len(parts) > max_parts else parts
    ns = "__".join(tail) if tail else "root"
    return sanitize_mermaid_id(ns)

def short_class_id(class_name: str, module: str) -> str:
    """
    짧고 유니크한 Mermaid ID: ClassName__<6-hex>
    (모듈+클래스 조합을 해시하여 충돌 방지)
    """
    h = hashlib.md5(f"{module}:{class_name}".encode("utf-8")).hexdigest()[:6]
    base = sanitize_mermaid_id(class_name)
    if not base or not base[0].isalpha():
        base = "C_" + base
    return f"{base}__{h}"

# ---------------- models ----------------
class ClassInfo:
    __slots__ = ("name", "module", "methods", "bases", "span")
    def __init__(self, name: str, module: str, span: Tuple[int,int]=(0,0)):
        self.name = name
        self.module = module      # 루트 상대 모듈 경로 (a.b.c)
        self.methods: List[str] = []
        self.bases: List[str] = []
        self.span = span

# ---------------- parsing ----------------
def safe_read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def extract_name_from_node(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        parts.reverse()
        return ".".join(parts)
    return ""

def module_name_from_path(root: Path, path: Path) -> str:
    """루트 기준 상대 경로를 . 으로 잇는 모듈명 생성"""
    rel = path.relative_to(root)
    parts = list(rel.parts)
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)

def parse_classes(root: Path, py_path: Path) -> Tuple[List["ClassInfo"], ast.AST, str]:
    src = safe_read_text(py_path)
    if not src.strip():
        return [], None, ""
    try:
        tree = ast.parse(src)
    except Exception:
        return [], None, src
    module = module_name_from_path(root, py_path)
    out: List[ClassInfo] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            start = getattr(node, "lineno", 0)
            end = getattr(node, "end_lineno", start)
            ci = ClassInfo(node.name, module, (start, end))
            for b in node.bases:
                bname = extract_name_from_node(b)
                if bname:
                    ci.bases.append(bname.split(".")[-1])
            for b in node.body:
                if isinstance(b, ast.FunctionDef):
                    ci.methods.append(b.name)
            out.append(ci)
    return out, tree, src

# ---------------- import context ----------------
class ImportContext(ast.NodeVisitor):
    def __init__(self):
        self.alias_to_module: Dict[str, str] = {}   # alias -> module path
        self.symbol_to_module: Dict[str, str] = {}  # symbol -> module path

    def visit_Import(self, node: ast.Import):
        for a in node.names:
            local = a.asname or a.name
            self.alias_to_module[local] = a.name

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for a in node.names:
            local = a.asname or a.name
            self.symbol_to_module[local] = mod

def build_import_context(tree: ast.AST) -> ImportContext:
    ctx = ImportContext()
    if isinstance(tree, ast.AST):
        ctx.visit(tree)
    return ctx

# ---------------- edge finder ----------------
def resolve_symbol_to_class(name: str, import_ctx: ImportContext,
                            project_index: Dict[str, Set[str]]) -> str:
    if not name:
        return ""
    parts = name.split(".")
    # 단일 토큰: 심볼
    if len(parts) == 1:
        sym = parts[0]
        if sym in import_ctx.symbol_to_module:
            return sym
        return sym
    # alias 체인
    head, *tail = parts
    base_mod = import_ctx.alias_to_module.get(head)
    if base_mod:
        class_name = tail[-1]
        if class_name:
            if len(tail) >= 2:
                mod_cand = base_mod + "." + ".".join(tail[:-1])
            else:
                mod_cand = base_mod
            # 모듈 후보 내 클래스 존재 확인(대략)
            if any((mod_cand == m or mod_cand.startswith(m)) and class_name in s
                   for m, s in project_index.items()):
                return class_name
            if class_name in project_index.get(base_mod, set()):
                return class_name
    # 끝 토큰을 클래스 후보로
    return parts[-1]

def find_edges_in_file(tree: ast.AST, src: str,
                       known_class_names: Set[str],
                       classes_in_file: List[ClassInfo],
                       project_index: Dict[str, Set[str]]) -> Set[Tuple[str,str,str]]:
    edges: Set[Tuple[str,str,str]] = set()
    if tree is None:
        return edges

    import_ctx = build_import_context(tree)
    current_class = None
    var_types_stack: List[Dict[str,str]] = []

    def push(): var_types_stack.append({})
    def pop():
        if var_types_stack: var_types_stack.pop()
    def setv(n,k):
        if var_types_stack: var_types_stack[-1][n] = k
    def getv(n):
        for scope in reversed(var_types_stack):
            if n in scope: return scope[n]
        return ""

    class V(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef):
            nonlocal current_class
            prev = current_class
            current_class = node.name
            self.generic_visit(node)
            current_class = prev

        def visit_FunctionDef(self, node: ast.FunctionDef):
            push()
            self.generic_visit(node)
            pop()

        def visit_Assign(self, node: ast.Assign):
            if not current_class:
                return self.generic_visit(node)
            rhs_cls = ""
            if isinstance(node.value, ast.Call):
                callee = extract_name_from_node(node.value.func)
                cand = resolve_symbol_to_class(callee, import_ctx, project_index)
                if cand in known_class_names and cand != current_class:
                    rhs_cls = cand
                    edges.add((current_class, cand, "uses"))
            for t in node.targets:
                # self.attr = Class(...)
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                    if rhs_cls:
                        edges.add((current_class, rhs_cls, "has"))
                    elif isinstance(node.value, ast.Name):
                        v = getv(node.value.id)
                        if v and v != current_class:
                            edges.add((current_class, v, "has"))
                # x = Class(...)
                elif isinstance(t, ast.Name) and rhs_cls:
                    setv(t.id, rhs_cls)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign):
            if not current_class:
                return self.generic_visit(node)
            if isinstance(node.target, ast.Attribute):
                if isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
                    ann = extract_name_from_node(node.annotation)
                    cand = resolve_symbol_to_class(ann, import_ctx, project_index)
                    if cand in known_class_names and cand != current_class:
                        edges.add((current_class, cand, "has"))
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call):
            if not current_class:
                return self.generic_visit(node)
            callee = extract_name_from_node(node.func)
            cand = resolve_symbol_to_class(callee, import_ctx, project_index)
            if cand in known_class_names and cand != current_class:
                edges.add((current_class, cand, "uses"))
            self.generic_visit(node)

    V().visit(tree)

    # Fallback: 클래스 본문 텍스트에서 KnownClass( 보조 스캔
    if src:
        lines = src.splitlines()
        for ci in classes_in_file:
            s, e = ci.span
            s = max(1, s); e = max(e, s)
            text = "\n".join(lines[s-1:e])
            for k in known_class_names:
                if len(k) < 3:
                    continue
                if re.search(rf"\b{k}\s*\(", text):
                    if k != ci.name:
                        edges.add((ci.name, k, "uses"))
    return edges

# ---------------- emitter ----------------
def write_mermaid(classes_by_module: Dict[str, List[ClassInfo]],
                  inherits_in: List[Tuple[str,str,str]],
                  edges_in: List[Tuple[str,str,str,str]],
                  out_path: Path, max_methods: int):
    # Build ids (짧은 ID)
    class_id_map: Dict[Tuple[str,str], str] = {}
    name_to_ids: Dict[str, List[str]] = {}
    id_to_module: Dict[str, str] = {}

    for module, lst in classes_by_module.items():
        for ci in lst:
            cid = short_class_id(ci.name, module)
            class_id_map[(module, ci.name)] = cid
            id_to_module[cid] = module
            name_to_ids.setdefault(ci.name, []).append(cid)

    lines: List[str] = ["classDiagram"]

    # Classes (alias 없음, 블록만)
    for module, lst in sorted(classes_by_module.items()):
        ns_id = short_namespace_id(module, max_parts=3)
        lines.append(f"namespace {ns_id} {{")
        for ci in sorted(lst, key=lambda x: x.name):
            cid = class_id_map[(module, ci.name)]
            lines.append(f"  class {cid} {{")
            for m in ci.methods[:max_methods]:
                lines.append(f"    +{m}()")
            if len(ci.methods) > max_methods:
                lines.append(f"    ..({len(ci.methods)-max_methods} more)..")
            lines.append("  }")
        lines.append("}")

    def resolve_target_id(current_module: str, target_name: str) -> str:
        cands = name_to_ids.get(target_name, [])
        if not cands:
            return ""
        same = [cid for cid in cands if id_to_module.get(cid) == current_module]
        if same:
            return same[0]
        if len(cands) == 1:
            return cands[0]
        return ""  # ambiguous

    # Inheritance
    for mod, cls, base in inherits_in:
        derived_id = class_id_map.get((mod, cls))
        if not derived_id:
            continue
        base_id = resolve_target_id(mod, base)
        if base_id:
            lines.append(f"{base_id} <|-- {derived_id}")

    # uses / has
    for mod, cls, tgt, rel in edges_in:
        src_id = class_id_map.get((mod, cls))
        if not src_id:
            continue
        dst_id = resolve_target_id(mod, tgt)
        if not dst_id or dst_id == src_id:
            continue
        arrow = "-->" if rel == "uses" else "*--"
        lines.append(f"{src_id} {arrow} {dst_id} : {rel}")

    out_path.write_text("\n".join(lines), encoding="utf-8")

# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="Project/package root directory")
    ap.add_argument("-o", "--output", type=Path, default=Path("docs/diagrams/uml_class_diagram.mmd"))
    ap.add_argument("--max-methods", type=int, default=12)
    ap.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDES))
    args = ap.parse_args()

    root: Path = args.root.resolve()
    out_path: Path = (root / args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    excludes = set(args.exclude)

    classes_by_module: Dict[str, List[ClassInfo]] = {}
    all_class_names: Set[str] = set()
    inherits_raw: List[Tuple[str,str,str]] = []
    edges_raw: List[Tuple[str,str,str,str]] = []

    parsed: Dict[Path, Tuple[List[ClassInfo], ast.AST, str]] = {}

    # 1) scan
    for py in iter_py_files(root, excludes):
        cls_list, tree, src = parse_classes(root, py)
        parsed[py] = (cls_list, tree, src)
        if not cls_list:
            continue
        module = cls_list[0].module
        classes_by_module.setdefault(module, []).extend(cls_list)
        for c in cls_list:
            all_class_names.add(c.name)
            for b in c.bases:
                inherits_raw.append((module, c.name, b))

    # 2) index
    project_index: Dict[str, Set[str]] = {mod: {c.name for c in lst}
                                          for mod, lst in classes_by_module.items()}

    # 3) edges
    for py, (cls_list, tree, src) in parsed.items():
        if not cls_list:
            continue
        file_edges = find_edges_in_file(tree, src, all_class_names, cls_list, project_index)
        module = cls_list[0].module
        for (a, b, rel) in file_edges:
            edges_raw.append((module, a, b, rel))

    # 4) write
    write_mermaid(classes_by_module, inherits_raw, edges_raw, out_path, args.max_methods)
    print(f"[OK] Mermaid UML written to: {out_path}")

if __name__ == "__main__":
    main()
