#!/usr/bin/env python3
"""
generate_mermaid_uml.py

Recursively scans a Python package, parses classes with AST, and produces a Mermaid
"classDiagram" UML file. Captures:
- Classes with up to N methods
- Inheritance
- Simple composition/usage edges via:
  - self.attr = ClassName(...)
  - self.attr: ClassName
  - ClassName(...) calls inside methods ("uses" heuristic)

USAGE:
  python generate_mermaid_uml.py /path/to/project -o uml_class_diagram.mmd --max-methods 12 --exclude .venv __pycache__ .mypy_cache
"""
import ast
import argparse
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

DEFAULT_EXCLUDES = {".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".git"}

def should_skip(path: Path, excludes: Set[str]) -> bool:
    return any(part in excludes for part in path.parts)

def iter_py_files(root: Path, excludes: Set[str]):
    for p in root.rglob("*.py"):
        if should_skip(p, excludes):
            continue
        yield p

class ClassInfo:
    __slots__ = ("name", "qualname", "module", "bases", "methods")
    def __init__(self, name: str, qualname: str, module: str):
        self.name = name
        self.qualname = qualname
        self.module = module
        self.bases: List[str] = []
        self.methods: List[str] = []

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
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        parts.reverse()
        return ".".join(parts)
    return ""

def parse_classes(py_path: Path) -> Tuple[List["ClassInfo"], ast.AST, str]:
    src = safe_read_text(py_path)
    if not src.strip():
        return [], None, ""
    try:
        tree = ast.parse(src)
    except Exception:
        return [], None, src
    module = module_name_from_path(py_path)
    classes: List[ClassInfo] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            ci = ClassInfo(node.name, f"{module}:{node.name}", module)
            for b in node.bases:
                bname = extract_name_from_node(b)
                if bname:
                    ci.bases.append(bname.split(".")[-1])
            for b in node.body:
                if isinstance(b, ast.FunctionDef):
                    ci.methods.append(b.name)
            classes.append(ci)
    return classes, tree, src

def module_name_from_path(path: Path) -> str:
    parts = list(path.parts)
    if parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)

def find_compositions_and_uses(tree: ast.AST, src: str, known_classes: Set[str]):
    edges = set()
    current_class = None
    class_stack: List[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef):
            nonlocal current_class
            class_stack.append(node.name)
            prev = current_class
            current_class = node.name
            self.generic_visit(node)
            current_class = prev
            class_stack.pop()

        def visit_Assign(self, node: ast.Assign):
            nonlocal current_class
            if current_class:
                for t in node.targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                        if isinstance(node.value, ast.Call):
                            callee = extract_name_from_node(node.value.func)
                            short = callee.split(".")[-1] if callee else ""
                            if short in known_classes and short != current_class:
                                edges.add((current_class, short, "has"))
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign):
            nonlocal current_class
            if current_class and isinstance(node.target, ast.Attribute):
                if isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
                    ann = extract_name_from_node(node.annotation)
                    short = ann.split(".")[-1] if ann else ""
                    if short in known_classes and short != current_class:
                        edges.add((current_class, short, "has"))
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call):
            nonlocal current_class
            if current_class:
                callee = extract_name_from_node(node.func)
                short = callee.split(".")[-1] if callee else ""
                if short in known_classes and short != current_class:
                    edges.add((current_class, short, "uses"))
            self.generic_visit(node)

    if tree is not None:
        Visitor().visit(tree)
    else:
        calls = re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\(", src or "")
        for callee in calls:
            if current_class and callee in known_classes:
                edges.add((current_class, callee, "uses"))
    return edges

def sanitize_mermaid_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s)

def write_mermaid(classes_by_module: Dict[str, List[ClassInfo]],
                  inherits, edges, out_path: Path, max_methods: int):
    lines: List[str] = ["classDiagram"]
    for module, cls_list in sorted(classes_by_module.items()):
        ns = sanitize_mermaid_id(module)
        lines.append(f'namespace {ns} {{')
        for ci in sorted(cls_list, key=lambda c: c.name):
            cname = sanitize_mermaid_id(ci.name)
            lines.append(f"  class {cname} {{")
            for m in ci.methods[:max_methods]:
                lines.append(f"    +{m}()")
            if len(ci.methods) > max_methods:
                lines.append(f"    ..({len(ci.methods)-max_methods} more)..")
            lines.append("  }")
        lines.append("}")

    for base, derived in sorted(inherits):
        lines.append(f"{sanitize_mermaid_id(base)} <|-- {sanitize_mermaid_id(derived)}")

    for a, b, rel in sorted(edges):
        arrow = "-->" if rel == "uses" else "*--"
        lines.append(f"{sanitize_mermaid_id(a)} {arrow} {sanitize_mermaid_id(b)} : {rel}")

    out_path.write_text("\n".join(lines), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="Project/package root directory")
    ap.add_argument("-o", "--output", type=Path, default=Path("uml_class_diagram.mmd"))
    ap.add_argument("--max-methods", type=int, default=12)
    ap.add_argument("--exclude", nargs="*", default=list(DEFAULT_EXCLUDES))
    args = ap.parse_args()

    root: Path = args.root.resolve()
    excludes = set(args.exclude)

    classes_by_module: Dict[str, List[ClassInfo]] = {}
    all_classes: Set[str] = set()
    parsed: Dict[Path, Tuple[List[ClassInfo], ast.AST, str]] = {}

    for py in iter_py_files(root, excludes):
        cls, tree, src = parse_classes(py)
        parsed[py] = (cls, tree, src)
        if cls:
            module = cls[0].module if cls else module_name_from_path(py)
            classes_by_module.setdefault(module, []).extend(cls)
            for c in cls:
                all_classes.add(c.name)

    inherits = []
    for module, cls_list in classes_by_module.items():
        for c in cls_list:
            for base in c.bases:
                inherits.append((base, c.name))

    edges = set()
    for py, (cls_list, tree, src) in parsed.items():
        if not cls_list:
            continue
        comps_uses = find_compositions_and_uses(tree, src, all_classes)
        edges |= comps_uses

    write_mermaid(classes_by_module, inherits, edges, args.output, args.max_methods)
    print(f"[OK] Mermaid UML written to: {args.output}")

if __name__ == "__main__":
    main()
