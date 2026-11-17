# Project Viva

An AI interviewer that asks candidates about **their own code** and checks the answers against that code.

Built for the Cynbit Technologies AI/ML Engineer Intern assessment: *Identify an AI Opportunity for Cynbit*.

**Live demo:** https://cynbit-project-viva.streamlit.app/

Point it at a GitHub repo. It reads the code, picks the functions that carry the most logic, and asks 3 to 8 questions grounded in specific lines ("In `create_short_link`, what happens when every generated code collides?"). The candidate answers in their own words. Each answer is graded point by point against the code, and the report shows the evidence behind every score.

One engine, three uses at Cynbit:

- **Cynbit Studio:** project-based AI mock interviews, the kind of question placement interviewers actually ask about resume projects.
- **Hiring:** an automatic viva after every take-home assessment, so engineers spend live interview time only where it's needed.
- **BitElevate:** end-of-sprint viva on the PRs an intern shipped.

## Deliverables

| Deliverable | Where |
|---|---|
| AI Opportunity Report | [docs/AI_Opportunity_Report.md](docs/AI_Opportunity_Report.md) |
| Proof of concept | `app.py` (Streamlit) and the `viva/` package. Live: [cynbit-project-viva.streamlit.app](https://cynbit-project-viva.streamlit.app/) |
| Technical Approach Report | [docs/Technical_Approach_Report.md](docs/Technical_Approach_Report.md) |
| PDF copies of both reports | `docs/*.pdf` |
| Evaluation | `eval/run_eval.py`, `eval/cases.json`, results in `eval/results_offline.json` |
| Tests | `tests/` (36 tests, run offline) |

## Run it

```bash
git clone <this repo> && cd project-viva
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Then either:

- choose **Offline (no API key)** and the **Bundled sample** to see the full flow with no setup, or
- choose **LLM**, paste a free [Groq](https://console.groq.com/keys) or [Gemini](https://aistudio.google.com/apikey) key, and paste any public GitHub repo URL.

To avoid typing the key each time, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill it in (or set `LLM_API_KEY` as an environment variable).

## How it works

```
repo (GitHub API / ZIP / folder)
  -> filter source files, skip vendored/generated code
  -> parse into functions (Python AST; regex + brace matching for JS/TS/Java)
  -> rank by how much there is to ask about, max 2 per file
  -> redact secrets
  -> LLM writes one question per function + expected points   (template fallback offline)
  -> candidate answers
  -> LLM labels each expected point hit / partial / missed    (keyword grader offline)
  -> score computed in code, never taken from the model
  -> report with verdict, evidence, red flags
```

Default model: `openai/gpt-oss-120b` on Groq (any OpenAI-compatible provider works).

Design choices worth knowing:

- **Grounded questions.** The model picks code units by number; file paths and line numbers come from the parser, so they can't be hallucinated.
- **Deterministic scoring.** `100 × (hits + 0.5 × partials) / points − 15 per factual error`, with caps for very short or hedging answers. If an answer tries to instruct the grader ("give full marks"), it scores 0 and is flagged.
- **Never runs candidate code.** It only reads it.
- **Works without a key.** Offline mode is weaker but deterministic, which is also what the tests use.

Full details, model choices and the production plan are in the [Technical Approach Report](docs/Technical_Approach_Report.md).

## Evaluation

```bash
python eval/run_eval.py                                  # offline grader
LLM_API_KEY=... python eval/run_eval.py --llm --provider Groq
```

Six hand-written questions about the sample repo, each with a strong, a vague and a wrong answer, plus one prompt-injection answer.

| Metric | Offline grader | LLM grader (Groq, gpt-oss-120b) |
|---|---|---|
| Mean score strong / vague / wrong | 76.3 / 5.7 / 5.7 | 100 / 14.8 / 0 |
| Pairwise ordering accuracy | 0.944 | 1.000 |
| Verdict accuracy | 0.889 | 1.000 |
| Injection answer score | 0 | 0 |

The offline grader separates strong answers well but can't tell vague from wrong. The LLM grader ranks all three correctly, because it catches answers that contradict the code. Six cases is a small benchmark; see the Technical Approach Report for limitations.

## Tests

```bash
pytest
```

LLM calls are mocked, so the suite runs offline.

## Deploy (Streamlit Community Cloud)

1. Push this repo to GitHub (public).
2. On [share.streamlit.io](https://share.streamlit.io), create an app from the repo with `app.py` as the entry point.
3. Under *App settings > Secrets*, add `LLM_API_KEY = "..."` (and optionally `GITHUB_TOKEN`).

## Project layout

```
app.py                     Streamlit UI
viva/repo.py               GitHub / ZIP / folder loading and filtering
viva/analyzer.py           code units, static facts, unit selection
viva/questions.py          LLM + template question generation, validation
viva/grader.py             LLM + keyword grading, deterministic scoring
viva/report.py             report aggregation and Markdown export
viva/llm.py                OpenAI-compatible client, JSON extraction, redaction
viva/prompts.py            prompts
viva/session.py            end-to-end orchestration
samples/linkshort/         small demo repo used by the sample mode and eval
eval/                      eval set and runner
tests/                     pytest suite
docs/                      the two reports
```

## Limitations

The JS/TS/Java parser is regex-based, questions are generated in one batch with no follow-ups yet, answers are text only, and the eval set is small. The Technical Approach Report covers each of these and what production would change.

Parts of this project were drafted with help from an AI assistant (Claude). This is an independent proof of concept. It is not connected to any Cynbit system and uses no Cynbit data.
