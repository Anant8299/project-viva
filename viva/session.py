"""One viva end to end: files -> units -> questions -> grades -> report."""
from __future__ import annotations

from .analyzer import extract_units, select_units
from .grader import grade
from .llm import LLMClient
from .questions import Question, generate_llm, generate_offline
from .repo import RepoError, RepoFile
from .report import SessionReport


def build_questions(files: list[RepoFile], n: int = 5, client: LLMClient | None = None) -> tuple[list[Question], list[str]]:
    units = select_units(extract_units(files), n)
    if not units:
        raise RepoError("Found source files but no functions worth asking about.")
    warnings = []
    if len(units) < n:
        warnings.append(f"Repo is small: only {len(units)} code units were worth asking about.")
    if client:
        qs, w = generate_llm(client, units)
        return qs, warnings + w
    return generate_offline(units), warnings


def run_viva(repo_name: str, questions: list[Question], answers: dict[str, str],
             client: LLMClient | None = None) -> SessionReport:
    grades = [grade(q, answers.get(q.id, ""), client) for q in questions]
    return SessionReport(repo_name, questions, grades)
