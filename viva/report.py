"""Turn per-question grades into a reviewer-facing summary."""
from __future__ import annotations

from dataclasses import dataclass

from .grader import Grade, verdict_for
from .questions import Question

BAND_TEXT = {
    "understands": "Explains the submitted code with specifics. Low risk that the work is not their own.",
    "partial": "Knows the general shape but is vague on details. Worth a short live follow-up.",
    "weak": "Could not explain most of the code they submitted. Needs a live interview before moving forward.",
}


@dataclass
class SessionReport:
    repo: str
    questions: list[Question]
    grades: list[Grade]

    @property
    def overall(self) -> int:
        return round(sum(g.score for g in self.grades) / len(self.grades)) if self.grades else 0

    @property
    def band(self) -> str:
        return verdict_for(self.overall)

    @property
    def red_flags(self) -> list[str]:
        out = []
        weak = sum(g.verdict == "weak" for g in self.grades)
        if self.grades and weak / len(self.grades) >= 0.5:
            out.append(f"{weak} of {len(self.grades)} answers were weak")
        errors = sum(len(g.factual_errors) for g in self.grades)
        if errors >= 2:
            out.append(f"{errors} statements contradicted the code")
        for g in self.grades:
            if "answer tried to instruct the grader" in g.flags:
                out.append(f"{g.question_id}: answer tried to instruct the grader")
        short = sum("very short answer" in g.flags for g in self.grades)
        if short >= 2:
            out.append(f"{short} answers were very short")
        return out

    def to_markdown(self) -> str:
        lines = [
            f"# Project Viva report: {self.repo}", "",
            f"**Overall: {self.overall}/100 ({self.band})**", "", BAND_TEXT[self.band], "",
        ]
        if self.red_flags:
            lines += ["Red flags:"] + [f"- {f}" for f in self.red_flags] + [""]
        for q, g in zip(self.questions, self.grades):
            lines += [
                f"## {q.id}. `{q.unit_name}` ({q.file}:{q.start_line}-{q.end_line}) - {g.score}/100, {g.verdict}",
                "", f"> {q.question}", "",
            ]
            for p in g.points:
                mark = {"hit": "[x]", "partial": "[~]", "missed": "[ ]"}[p.status]
                lines.append(f"- {mark} {p.point}")
            if g.factual_errors:
                lines += ["", "Contradicts the code:"] + [f"- {e}" for e in g.factual_errors]
            if g.flags:
                lines += ["", "Flags: " + ", ".join(g.flags)]
            if g.feedback:
                lines += ["", g.feedback]
            lines.append("")
        lines.append(f"_Questions: {self.questions[0].method if self.questions else '-'}; "
                     f"grading: {self.grades[0].method if self.grades else '-'}._")
        return "\n".join(lines)
