"""Check that the grader ranks strong > vague > wrong answers.

    python eval/run_eval.py                 # offline grader
    LLM_API_KEY=... python eval/run_eval.py --llm --provider Groq

Writes eval/results_<mode>.json and prints a summary table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from viva.analyzer import extract_units  # noqa: E402
from viva.grader import grade  # noqa: E402
from viva.llm import LLMClient  # noqa: E402
from viva.questions import Question  # noqa: E402
from viva.repo import load_from_dir  # noqa: E402

ORDER = ["strong", "vague", "wrong"]
EXPECTED_VERDICT = {"strong": {"understands"}, "vague": {"partial", "weak"}, "wrong": {"weak"}}


def load_cases():
    data = json.loads((ROOT / "eval" / "cases.json").read_text())
    units = {(u.file, u.name): u for u in extract_units(load_from_dir(ROOT / data["repo"]))}
    questions = {}
    for c in data["cases"]:
        u = units[(c["file"], c["unit"])]
        questions[c["id"]] = Question(
            id=c["id"], file=u.file, unit_name=u.name, start_line=u.start, end_line=u.end, kind="eval",
            question=c["question"], expected_points=c["expected_points"], source=u.source, method="eval",
        )
    return data, questions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--provider", default="Groq")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    client = None
    if args.llm:
        key = os.getenv("LLM_API_KEY")
        if not key:
            sys.exit("Set LLM_API_KEY to run the LLM eval.")
        client = LLMClient(api_key=key, provider=args.provider, model=args.model)
    mode = f"llm-{args.provider.lower()}" if client else "offline"

    data, questions = load_cases()
    rows, scores = [], {k: [] for k in ORDER}
    pair_ok = pair_total = verdict_ok = verdict_total = 0
    for c in data["cases"]:
        q = questions[c["id"]]
        s = {}
        for label in ORDER:
            g = grade(q, c["answers"][label], client)
            s[label] = g.score
            scores[label].append(g.score)
            verdict_total += 1
            verdict_ok += g.verdict in EXPECTED_VERDICT[label]
            rows.append({"case": c["id"], "label": label, "score": g.score, "verdict": g.verdict,
                         "points": [p.status for p in g.points], "errors": g.factual_errors, "flags": g.flags})
        for hi, lo in [("strong", "vague"), ("vague", "wrong"), ("strong", "wrong")]:
            pair_total += 1
            # vague vs wrong may tie at 0; a tie there is acceptable, anything else must be strict
            pair_ok += s[hi] > s[lo] or (hi == "vague" and s[hi] == s[lo])
        print(f"{c['id']}  strong={s['strong']:>3}  vague={s['vague']:>3}  wrong={s['wrong']:>3}")

    inj = data["injection"]
    g_inj = grade(questions[inj["case"]], inj["answer"], client)
    print(f"injection attempt score={g_inj.score} flags={g_inj.flags}")

    summary = {
        "mode": mode,
        "mean_score": {k: round(mean(v), 1) for k, v in scores.items()},
        "pairwise_order_accuracy": round(pair_ok / pair_total, 3),
        "verdict_accuracy": round(verdict_ok / verdict_total, 3),
        "injection_score": g_inj.score,
        "n_cases": len(data["cases"]),
    }
    print(json.dumps(summary, indent=2))
    out = ROOT / "eval" / f"results_{mode}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
