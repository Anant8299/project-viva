"""Split source files into code units (functions/methods) with simple facts about each.

Python gets a real AST pass. Other languages get a regex + brace-matching pass, which is
rougher but good enough to locate functions and pull out the calls and error handling.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from .repo import RepoFile

BUILTINS = {
    "print", "len", "range", "str", "int", "float", "list", "dict", "set", "tuple", "isinstance",
    "super", "min", "max", "sum", "sorted", "reversed", "enumerate", "zip", "map", "filter",
    "open", "getattr", "setattr", "hasattr", "type", "bool", "any", "all", "abs", "round",
    "join", "append", "get", "items", "keys", "values", "strip", "split", "format", "lower",
    "upper", "replace", "startswith", "endswith", "pop", "update", "extend", "add",
    # JS / Java noise
    "if", "for", "while", "switch", "catch", "return", "function", "console", "log", "require",
    "push", "then", "parseInt", "toString", "equals", "println", "new", "JSON", "stringify", "parse",
}


@dataclass
class CodeUnit:
    file: str
    name: str
    kind: str              # "function" | "method"
    start: int             # 1-based, inclusive
    end: int
    source: str
    calls: list[str] = field(default_factory=list)
    catches: list[str] = field(default_factory=list)
    raises: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    returns: list[str] = field(default_factory=list)
    outcomes: dict[str, str] = field(default_factory=dict)  # condition -> what its branch does first
    loops: int = 0

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @property
    def is_test(self) -> bool:
        return "test" in self.file.lower() or self.name.startswith("test")

    def numbered_source(self) -> str:
        return "\n".join(f"{self.start + i:>4} | {line}" for i, line in enumerate(self.source.splitlines()))


def _dedupe(items):
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _is_exception_name(name: str) -> bool:
    return name[:1].isupper() and (name.endswith("Error") or name.endswith("Exception"))


def _short(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


class _PyVisitor(ast.NodeVisitor):
    def __init__(self, unit: CodeUnit):
        self.u = unit

    def visit_FunctionDef(self, node):
        # don't descend into nested functions twice; they are separate units
        if node.lineno != self.u.start:
            return
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        if name and name not in BUILTINS:
            self.u.calls.append(name)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.type is not None:
            self.u.catches.append(ast.unparse(node.type))
        else:
            self.u.catches.append("Exception")
        self.generic_visit(node)

    def visit_Raise(self, node):
        if node.exc is not None:
            exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            self.u.raises.append(ast.unparse(exc))
        self.generic_visit(node)

    def visit_If(self, node):
        cond = _short(ast.unparse(node.test))
        self.u.conditions.append(cond)
        first = node.body[0] if node.body else None
        if isinstance(first, ast.Return) and first.value is not None:
            self.u.outcomes.setdefault(cond, "returns " + _short(ast.unparse(first.value), 60))
        elif isinstance(first, ast.Raise) and first.exc is not None:
            exc = first.exc.func if isinstance(first.exc, ast.Call) else first.exc
            self.u.outcomes.setdefault(cond, "raises " + ast.unparse(exc))
        self.generic_visit(node)

    def visit_Return(self, node):
        if node.value is not None:
            self.u.returns.append(_short(ast.unparse(node.value), 60))
        self.generic_visit(node)

    def visit_For(self, node):
        self.u.loops += 1
        self.generic_visit(node)

    visit_While = visit_For


def _python_units(f: RepoFile) -> list[CodeUnit]:
    try:
        tree = ast.parse(f.content)
    except SyntaxError:
        return []
    lines = f.lines
    units = []
    class_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_methods.add(id(child))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
        end = node.end_lineno or node.lineno
        unit = CodeUnit(
            file=f.path, name=node.name,
            kind="method" if id(node) in class_methods else "function",
            start=start, end=end, source="\n".join(lines[start - 1:end]),
        )
        unit.start = start
        _PyVisitor(unit).visit(node)
        unit.calls = [c for c in _dedupe(unit.calls) if not _is_exception_name(c)]
        unit.catches = _dedupe(unit.catches)
        unit.raises = _dedupe(unit.raises)
        unit.conditions = _dedupe(unit.conditions)
        unit.returns = _dedupe(unit.returns)
        units.append(unit)
    return sorted(units, key=lambda u: u.start)


_JS_FUNC = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*\("
    r"|^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"
    r"|^\s*(?:public|private|protected|static|final|async|\s)+[\w<>\[\],\s]*?\s(\w+)\s*\([^;]*\)\s*(?:throws [\w.,\s]+)?\{"
    r"|^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{"
)
_JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return", "else", "constructor"}


def _brace_end(lines: list[str], start_idx: int) -> int:
    depth, seen = 0, False
    for i in range(start_idx, len(lines)):
        for ch in lines[i]:
            if ch == "{":
                depth += 1
                seen = True
            elif ch == "}":
                depth -= 1
        if seen and depth <= 0:
            return i
        if not seen and i > start_idx and "=>" in lines[start_idx]:
            return i  # one-line arrow function body on the next line
    return min(len(lines) - 1, start_idx + 40)


def _generic_units(f: RepoFile) -> list[CodeUnit]:
    lines = f.lines
    units = []
    i = 0
    while i < len(lines):
        m = _JS_FUNC.match(lines[i])
        name = next((g for g in m.groups() if g), None) if m else None
        if not name or name in _JS_KEYWORDS:
            i += 1
            continue
        end = _brace_end(lines, i)
        body = "\n".join(lines[i:end + 1])
        unit = CodeUnit(file=f.path, name=name, kind="function", start=i + 1, end=end + 1, source=body)
        inner = "\n".join(lines[i + 1:end + 1])
        unit.calls = _dedupe(c for c in re.findall(r"\b([A-Za-z_]\w*)\s*\(", inner) if c not in BUILTINS and c != name)
        unit.calls = [c for c in unit.calls if not _is_exception_name(c)]
        unit.catches = _dedupe(re.findall(r"catch\s*\(\s*(?:final\s+)?([\w.]+)", body))
        unit.raises = _dedupe(re.findall(r"throw\s+new\s+(\w+)", body))
        unit.conditions = _dedupe(_short(c) for c in re.findall(r"\bif\s*\((.+?)\)\s*\{?\s*$", body, re.M))
        unit.returns = _dedupe(_short(r, 60) for r in re.findall(r"\breturn\s+(.+?);?\s*$", body, re.M))
        unit.loops = len(re.findall(r"\b(for|while)\s*\(", body)) + len(re.findall(r"\.(forEach|map)\(", body))
        units.append(unit)
        i = end + 1
    return units


def extract_units(files: list[RepoFile]) -> list[CodeUnit]:
    units = []
    for f in files:
        units.extend(_python_units(f) if f.path.endswith(".py") else _generic_units(f))
    return units


def interest_score(u: CodeUnit) -> float:
    """How much there is to ask about. Long, branchy, error-handling code scores high."""
    if u.length < 4 or u.is_test or u.name.startswith("__") and u.name != "__init__":
        return 0.0
    score = (
        2.0 * len(u.catches) + 1.5 * len(u.raises) + 1.2 * len(u.conditions)
        + 0.8 * min(len(u.calls), 5) + 1.0 * u.loops + 0.6 * min(len(u.returns), 3)
    )
    score += min(u.length, 40) / 10
    if u.length > 120:
        score *= 0.7  # huge functions are hard to answer about in a few lines
    return round(score, 2)


def select_units(units: list[CodeUnit], n: int, per_file: int = 2) -> list[CodeUnit]:
    ranked = sorted((u for u in units if interest_score(u) > 0), key=interest_score, reverse=True)
    chosen, per = [], {}
    for u in ranked:
        if per.get(u.file, 0) >= per_file:
            continue
        chosen.append(u)
        per[u.file] = per.get(u.file, 0) + 1
        if len(chosen) == n:
            break
    if len(chosen) < n:  # small repo: relax the per-file cap
        for u in ranked:
            if u not in chosen:
                chosen.append(u)
                if len(chosen) == n:
                    break
    return chosen
