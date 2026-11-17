"""Grade answers against expected points.

The final score is always computed here from per-point labels, never taken from the model.
That keeps scores stable across runs and stops a model from being talked into "100/100".
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .llm import LLMClient, LLMError, redact
from .prompts import GRADE_SYSTEM, grade_user_prompt
from .questions import Question

POINT_VALUE = {"hit": 1.0, "partial": 0.5, "missed": 0.0}
ERROR_PENALTY = 15
SHORT_ANSWER_WORDS = 12
SHORT_ANSWER_CAP = 40
HEDGES = ("i think", "maybe", "not sure", "probably", "i guess", "kind of", "sort of", "i don't remember",
          "dont remember", "no idea")
FRAME_WORDS = {"catches", "catch", "raises", "raise", "returns", "return", "calls", "call", "checks", "check",
               "defines", "the", "a", "an", "of", "to", "in", "is", "it", "and", "or", "if", "when", "on", "for",
               "with", "by", "be", "that", "this", "none", "not", "fail", "fails", "code", "otherwise"}
# Words that show up in almost any answer. They only count when a point has nothing more specific.
GENERIC = {"error", "exception", "value", "data", "function", "method", "result", "list", "dict", "string",
           "true", "false", "self", "request", "user", "handle", "handler"}
INJECTION = re.compile(r"(?i)(ignore (all |the )?(previous|above) instructions|give (me )?(full|100|maximum) (marks|score)|"
                       r"you are now|system prompt)")


@dataclass
class PointResult:
    point: str
    status: str
    evidence: str = ""


@dataclass
class Grade:
    question_id: str
    score: int
    verdict: str
    points: list[PointResult]
    factual_errors: list[str] = field(default_factory=list)
    feedback: str = ""
    flags: list[str] = field(default_factory=list)
    method: str = "offline"

    def to_dict(self) -> dict:
        return asdict(self)


def verdict_for(score: int) -> str:
    if score >= 70:
        return "understands"
    if score >= 40:
        return "partial"
    return "weak"


def _stem(word: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(word) > 4 and word.endswith(suf):
            return word[: -len(suf)]
    return word


def tokens(text: str) -> set[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)      # camelCase -> camel Case
    words = re.findall(r"[a-zA-Z0-9]+", text.replace("_", " ").lower())
    return {_stem(w) for w in words if w not in FRAME_WORDS and len(w) > 1}


def _flags(answer: str) -> list[str]:
    flags = []
    words = len(answer.split())
    low = answer.lower()
    if words < SHORT_ANSWER_WORDS:
        flags.append("very short answer")
    if sum(low.count(h) for h in HEDGES) >= 2:
        flags.append("lots of hedging")
    if INJECTION.search(answer):
        flags.append("answer tried to instruct the grader")
    return flags


def _final_score(points: list[PointResult], n_errors: int, flags: list[str]) -> int:
    if not points:
        return 0
    raw = 100 * sum(POINT_VALUE.get(p.status, 0) for p in points) / len(points)
    raw -= ERROR_PENALTY * n_errors
    if "very short answer" in flags:
        raw = min(raw, SHORT_ANSWER_CAP)
    if "lots of hedging" in flags:
        raw -= 10
    if "answer tried to instruct the grader" in flags:
        raw = 0
    return int(max(0, min(100, round(raw))))


def grade_offline(q: Question, answer: str) -> Grade:
    answer = answer or ""
    flags = _flags(answer)
    ans = tokens(answer)
    results = []
    for point in q.expected_points:
        pt = tokens(point)
        specific = pt - GENERIC
        pt = specific or pt
        if not pt:
            results.append(PointResult(point, "missed"))
            continue
        overlap = len(pt & ans) / len(pt)
        status = "hit" if overlap >= 0.6 else "partial" if overlap >= 0.3 else "missed"
        results.append(PointResult(point, status, ", ".join(sorted(pt & ans))))
    score = _final_score(results, 0, flags) if answer.strip() else 0
    hit = [p.point for p in results if p.status == "hit"]
    missed = [p.point for p in results if p.status != "hit"]
    fb = []
    if hit:
        fb.append("Covered: " + "; ".join(hit) + ".")
    if missed:
        fb.append("Revisit: " + "; ".join(missed) + ".")
    return Grade(q.id, score, verdict_for(score), results, [], " ".join(fb), flags, "offline")


def grade_llm(client: LLMClient, q: Question, answer: str) -> Grade:
    answer = answer or ""
    if not answer.strip():
        return Grade(q.id, 0, "weak", [PointResult(p, "missed") for p in q.expected_points], [],
                     "No answer given.", ["empty answer"], "llm")
    flags = _flags(answer)
    try:
        data = client.chat_json(GRADE_SYSTEM, grade_user_prompt(q, redact(q.source), answer))
    except LLMError:
        g = grade_offline(q, answer)
        g.flags.append("LLM grading failed, offline grader used")
        return g
    labels = {}
    for item in data.get("points", []) if isinstance(data, dict) else []:
        if isinstance(item, dict) and item.get("status") in POINT_VALUE:
            labels[str(item.get("point", "")).strip().lower()] = item
    results = []
    for i, point in enumerate(q.expected_points):
        item = labels.get(point.strip().lower())
        if item is None:  # model paraphrased the point text; fall back to position
            raw = data.get("points", [])
            item = raw[i] if i < len(raw) and isinstance(raw[i], dict) else {"status": "missed"}
        status = item.get("status") if item.get("status") in POINT_VALUE else "missed"
        results.append(PointResult(point, status, str(item.get("evidence", ""))[:200]))
    errors = [str(e) for e in data.get("factual_errors", []) if str(e).strip()][:5]
    score = _final_score(results, len(errors), flags)
    return Grade(q.id, score, verdict_for(score), results, errors, str(data.get("feedback", "")), flags, "llm")


def grade(q: Question, answer: str, client: LLMClient | None = None) -> Grade:
    return grade_llm(client, q, answer) if client else grade_offline(q, answer)
