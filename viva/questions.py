"""Generate viva questions grounded in specific code units."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .analyzer import CodeUnit
from .llm import LLMClient, LLMError, redact
from .prompts import QUESTION_SYSTEM, question_user_prompt

VALID_KINDS = {"why", "edge_case", "what_if", "data_flow", "failure"}


@dataclass
class Question:
    id: str
    file: str
    unit_name: str
    start_line: int
    end_line: int
    kind: str
    question: str
    expected_points: list[str]
    source: str = field(repr=False, default="")
    method: str = "offline"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("source")
        return d


def _offline_options(u: CodeUnit) -> list[tuple[str, str, list[str]]]:
    """All template questions that fit this unit, as (kind, question, expected_points)."""
    where = f"`{u.name}` in `{u.file}` (lines {u.start}-{u.end})"
    opts = []
    if u.catches or u.raises:
        pts = [f"catches {c}" for c in u.catches[:2]] + [f"raises {r}" for r in u.raises[:2]]
        opts.append(("failure", f"{where} deals with things going wrong. What can fail here, and what does "
                                "the code do in each case?", pts))
    if u.conditions:
        cond = next((c for c in u.conditions if c in u.outcomes), u.conditions[0])
        pts = [f"checks {cond}"]
        if cond in u.outcomes:
            pts.append(f"when it fails the code {u.outcomes[cond]}")
        opts.append(("what_if", f"In {where}, what would go wrong if the check `{cond}` were removed?", pts))
    if len(u.conditions) >= 2:
        opts.append(("edge_case", f"Walk me through the decisions {where} makes. What are the main cases and "
                                  "what happens in each?", [f"checks {c}" for c in u.conditions[:3]]))
    if u.calls:
        pts = [f"calls {c}" for c in u.calls[:3]]
        if u.loops:
            q = f"Explain how data moves through {where}. What does the loop do, and what comes out at the end?"
        else:
            q = f"{where} relies on other code. Which functions does it call, and what does it use each one for?"
        opts.append(("data_flow", q, pts))
    if u.returns:
        opts.append(("why", f"What does {where} return, and when would the rest of the app call it?",
                     [f"returns {r}" for r in u.returns[:2]]))
    if not opts:
        opts.append(("why", f"What is {where} for, and why does it exist as its own function?", [f"defines {u.name}"]))
    return opts


def _make(u: CodeUnit, idx: int, option: tuple[str, str, list[str]]) -> Question:
    kind, text, pts = option
    return Question(
        id=f"q{idx}", file=u.file, unit_name=u.name, start_line=u.start, end_line=u.end,
        kind=kind, question=text, expected_points=pts[:4], source=u.source, method="offline",
    )


def _offline_question(u: CodeUnit, idx: int) -> Question:
    """Template question from static facts. Weaker than the LLM, but deterministic and free."""
    return _make(u, idx, _offline_options(u)[0])


def generate_offline(units: list[CodeUnit]) -> list[Question]:
    """Pick one template per unit, spreading question kinds so the viva doesn't repeat itself."""
    used: dict[str, int] = {}
    out = []
    for i, u in enumerate(units, 1):
        opts = _offline_options(u)
        best = min(opts, key=lambda o: (used.get(o[0], 0), opts.index(o)))
        used[best[0]] = used.get(best[0], 0) + 1
        out.append(_make(u, i, best))
    return out


def _validate(item: dict, units: list[CodeUnit], used: set[int]) -> Question | None:
    try:
        n = int(item.get("unit"))
    except (TypeError, ValueError):
        return None
    if not 1 <= n <= len(units) or n in used:
        return None
    text = str(item.get("question", "")).strip()
    points = [str(p).strip() for p in item.get("expected_points", []) if str(p).strip()]
    if len(text) < 15 or not 1 <= len(points) <= 6:
        return None
    u = units[n - 1]
    kind = item.get("kind") if item.get("kind") in VALID_KINDS else "why"
    used.add(n)
    return Question(
        id="", file=u.file, unit_name=u.name, start_line=u.start, end_line=u.end,
        kind=kind, question=text, expected_points=points[:4], source=u.source, method="llm",
    )


def generate_llm(client: LLMClient, units: list[CodeUnit]) -> tuple[list[Question], list[str]]:
    """Returns questions plus warnings. Any unit the model skipped or botched gets an offline question."""
    warnings = []
    safe_units = [CodeUnit(**{**u.__dict__, "source": redact(u.source)}) for u in units]
    try:
        data = client.chat_json(QUESTION_SYSTEM, question_user_prompt(safe_units, len(units)))
        items = data.get("questions", []) if isinstance(data, dict) else []
    except LLMError as exc:
        warnings.append(f"LLM question generation failed, used offline questions instead ({exc}).")
        items = []
    used: set[int] = set()
    by_unit: dict[int, Question] = {}
    for item in items:
        q = _validate(item, units, used)
        if q:
            by_unit[int(item["unit"])] = q
    out = []
    for i, u in enumerate(units, 1):
        q = by_unit.get(i)
        if q is None:
            if items:
                warnings.append(f"Model gave no usable question for `{u.name}`; used a template question.")
            q = _offline_question(u, i)
        q.id = f"q{i}"
        out.append(q)
    return out, warnings
