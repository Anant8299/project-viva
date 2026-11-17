# Technical Approach Report: Project Viva

**Author:** Anant Pandey  
**Date:** November 2026

This document covers how the proof of concept works, why each choice was made, how it was evaluated, and what it would take to run it in production at Cynbit.

## 1. Problem, stated precisely

Input: a repository the candidate says they wrote.
Output: a short report saying how well the candidate can explain that code, with evidence for every judgement.

Constraints that shaped the design:

- Questions must be about *this* repo. A generic question ("what is a REST API?") tells you nothing about who wrote the code.
- Grading must be repeatable. Two runs over the same answer should give the same score, and the score must not be something the model can be argued into.
- The system must never execute candidate code.
- It must still work, in a reduced form, with no API key (for demos, CI and offline use).

## 2. Architecture

![Project Viva architecture](architecture.png)

| Module | Job |
|---|---|
| `viva/repo.py` | Loads files from the GitHub REST API (tree + contents endpoints), a ZIP upload or a local folder. Skips vendored and generated code (`node_modules`, `migrations`, minified JS, lockfiles), very small and very large files, and caps the repo at 40 files. Core-looking paths (`api`, `service`, `model`, `store`, ...) are fetched first. |
| `viva/analyzer.py` | Splits files into code units (functions and methods) and records facts about each: calls, caught and raised exceptions, `if` conditions and what each branch does first, return expressions, loops. Python uses the `ast` module; other languages use a regex plus brace matching, which is rougher but finds functions reliably. |
| `viva/analyzer.select_units` | Scores units by how much there is to ask about (error handling, branches, calls, loops, length) and picks the top N, at most two per file so the viva covers the repo instead of one big file. Tests, dunder methods and trivial getters are skipped. |
| `viva/questions.py` | Writes one question per selected unit, with 1 to 4 expected points. LLM path with validation, template fallback. |
| `viva/grader.py` | Labels each expected point as hit / partial / missed and turns the labels into a score. |
| `viva/report.py` | Aggregates per-question grades into an overall score, a verdict band and red flags, and exports Markdown or JSON. |
| `app.py` | Streamlit UI: pick repo, generate questions, answer, see report. A "reviewer view" toggle hides code and expected points while the candidate answers. |

## 3. Model choices

**Default: Llama 3.3 70B through Groq.** It follows JSON instructions well, is fast enough that a 5-question viva is generated in a few seconds, and Groq has a free tier, which matters for a PoC and for Studio's student-facing usage.

**Drop-in alternatives:** Gemini 2.5 Flash (free tier, long context) or GPT-4o-mini. All three are called through the OpenAI-compatible chat API, so switching is a config change (`viva/llm.py`, `PROVIDERS`). A self-hosted open model behind vLLM would use the same client, which is the route I would take if Cynbit does not want candidate code leaving its infrastructure.

**Temperature 0** for both question writing and grading. Variety in questions comes from the code itself, not from sampling.

**Why not fine-tune?** There is no labelled data yet. The right order is: ship with prompting, collect reviewer verdicts during the pilot, then use that data first to calibrate thresholds and only later, if needed, to fine-tune a smaller model for grading.

**Why not let the LLM do everything?** Static analysis is cheaper and more reliable at the parts that must be exact: which functions exist, their line numbers, what they call. The LLM is only used for the parts that need judgement (writing a good question, deciding whether an explanation matches the code).

## 4. Data pipeline

1. **Fetch.** `GET /repos/{owner}/{repo}` for the default branch, `GET /git/trees/{ref}?recursive=1` for the file list, then `GET /contents/{path}` per selected file. That is 2 + up to 40 requests, inside GitHub's anonymous limit of 60 requests per hour for one viva; an optional token raises it. ZIP upload avoids the API entirely.
2. **Filter.** Source extensions only, size between 150 bytes and 60 KB, skip vendored and generated directories.
3. **Parse.** Each file becomes code units with line ranges and facts.
4. **Select.** Interest score, per-file cap, top N.
5. **Redact.** Before anything is sent to an LLM, assignments to names containing `key`, `secret`, `token` or `password`, and common key formats (`sk-...`, `gsk_...`, `ghp_...`, AWS and Google keys), are replaced with placeholders.
6. **Generate, answer, grade, report.**

Nothing is stored server-side in the PoC. Session state lives in the Streamlit session and disappears when the tab closes.

## 5. Prompt design

Both prompts are in `viva/prompts.py`.

**Question writer.**

- Each code unit is sent inside `<code_unit number="i" file="..." lines="...">` tags, with line numbers on every line. The model refers to a unit by number, so it never has to reproduce file paths or line numbers, which are filled in from the parser.
- The system prompt asks for questions about reasoning (why, edge cases, what-if, data flow, failure handling) that can be answered from memory in 3 to 6 sentences, and forbids quoting large chunks of code back.
- Each question must come with 2 to 4 expected points, each a short, checkable fact that names the function, variable, exception or condition involved. These points are what make grading consistent.
- The model is told that everything inside `<code_unit>` is untrusted data. A comment in the repo saying "ignore previous instructions" is just text.
- Output is JSON mode. The reply is then validated: unit number in range and not repeated, question long enough, 1 to 6 points. Any unit the model skipped or got wrong gets a template question, so the viva always has N questions.

**Grader.**

- The grader sees the code, the question, the expected points and the answer, each in its own tags.
- For every expected point it returns `hit`, `partial` or `missed` with a short quote from the answer as evidence, plus a list of factual errors (claims that contradict the code, not omissions).
- It is told to be strict about vagueness and not to reward length or buzzwords.
- **The model never gives the score.** The score is computed in `grader._final_score`:
  `100 × (hits + 0.5 × partials) / points − 15 × factual errors`, capped at 40 for answers under 12 words, −10 for heavy hedging, and 0 if the answer tries to instruct the grader. If the model's reply includes its own "score" field it is ignored.
- If the model rewords a point's text, labels are matched by position instead.
- If the LLM call fails, that answer is graded by the offline grader and the report says so.

**Offline mode** uses the same pipeline. Questions come from templates filled with static facts (for example, "In `handle_create`, what would go wrong if the check `not user_id` were removed?" with the expected point taken from what that branch returns). The grader checks keyword overlap between each expected point and the answer, after splitting identifiers (`DuplicateCodeError` → duplicate, error) and ignoring generic words.

Verdict bands: 70+ "understands", 40-69 "partial", below 40 "weak".

## 6. Evaluation

`eval/cases.json` has six hand-written viva questions about the bundled sample repo. Each has three answers: **strong** (correct and specific), **vague** (true but generic) and **wrong** (confident and contradicts the code). There is also one prompt-injection answer. `eval/run_eval.py` grades all of them and reports:

- pairwise ordering accuracy (strong > vague, vague ≥ wrong, strong > wrong)
- verdict accuracy (strong → understands, vague → partial or weak, wrong → weak)
- the injection answer's score

Results for the offline grader (`python eval/run_eval.py`):

| Metric | Offline grader |
|---|---|
| Mean score, strong / vague / wrong | 76.3 / 5.7 / 5.7 |
| Pairwise ordering accuracy | 0.944 |
| Verdict accuracy | 0.889 |
| Injection answer score | 0 |

What this shows honestly: the keyword grader separates strong answers from the rest, but it **cannot tell vague answers from wrong ones**. Both score near zero, because it has no way to notice that "it counts requests in a fixed one-minute window" contradicts a token bucket. It can also be gamed by an answer that lists the right identifiers without explaining anything. That is the gap the LLM grader exists to close: it marks contradictions as factual errors and judges meaning, not word overlap.

To run the same eval with the LLM grader:

```bash
LLM_API_KEY=your_key python eval/run_eval.py --llm --provider Groq
```

It writes `eval/results_llm-groq.json`. I recommend running it before trusting the LLM grader on a new model; the eval takes under a minute.

The unit tests (`pytest`, 36 tests) cover URL parsing, file filtering, ZIP handling, the GitHub loader against a fake API, Python and JS analysis, question validation and top-up, score computation (including ignoring the model's own score), redaction, the injection rule, LLM failure fallbacks and an end-to-end offline session. LLM calls are mocked, so the suite runs offline in under a second.

## 7. Security and privacy

- Candidate code is **read, never executed**. No sandbox is needed because nothing runs.
- Repo content and answers are treated as untrusted in both prompts, and the score cannot be set by the model.
- Secrets are redacted before LLM calls. API keys are entered per session or through Streamlit secrets and are never written to disk by the app.
- For production: a data processing note to candidates, a retention policy for reports (for example, delete after the hiring decision), and the option of a self-hosted model.

## 8. Limitations of the PoC

- The JS/TS/Java analyzer is regex-based. It finds functions well but can miss nested arrow functions and some class syntax. Production should use tree-sitter for all languages.
- Questions are generated in one batch. A real interviewer asks follow-ups when an answer is weak; that is the most valuable next feature.
- Text answers only. Studio's mock interviews would want voice (speech-to-text in, text-to-speech out).
- The eval set is small and written by one person. The pilot's main job is to build a proper labelled set.
- Grading thresholds (70 / 40) are reasonable defaults, not calibrated against human reviewers yet.

## 9. Execution plan

| Phase | Time | What gets built | Exit criterion |
|---|---|---|---|
| 0. PoC | done | This repo: end-to-end loop, offline mode, eval harness, tests | Runs on any public repo |
| 1. Internal pilot | 2 weeks | Run every assessment submission in one hiring round through the viva. Senior engineers do their usual review blind to the viva result. | Viva and engineer agree on most candidates; no "understands" verdict where the engineer said "weak" |
| 2. Calibrate | 1 week | Use pilot labels to tune thresholds and the grader prompt, expand the eval set to 100+ answers, add tree-sitter parsing | Ordering accuracy ≥ 0.9 and verdict accuracy ≥ 0.85 with the LLM grader on the new set |
| 3. Follow-up questions | 2 weeks | After a partial or weak answer, the interviewer asks one targeted follow-up, then grades both together | Fewer borderline verdicts in the pilot set |
| 4. Studio launch | 2-3 weeks | Voice mode, per-student history, practice mode that shows the expected points after grading | Students complete vivas and come back for more |
| 5. Hiring and BitElevate integration | 2 weeks | Viva link sent automatically after an assessment submission; BitElevate end-of-sprint viva on the intern's merged PRs | Reviewer time per candidate drops measurably |

**Production architecture (sketch).** FastAPI service with endpoints `POST /vivas` (repo URL → questions), `POST /vivas/{id}/answers`, `GET /vivas/{id}/report`; Postgres for sessions, answers and reviewer labels; a worker queue for repo fetching and LLM calls; the same `viva` package as the core library. Studio, the hiring portal and BitElevate call the same API.

**Cost per viva.** Roughly one question-writing call (about 4-6k input tokens for 5 code units) and one grading call per question (about 1-2k tokens each), so around 10-15k tokens for a 5-question viva. On current free tiers that is free at pilot volume; at scale it should be checked against the chosen provider's pricing.
