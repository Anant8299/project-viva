# Submission notes

**Candidate:** Anant Pandey  
**Role:** AI/ML Engineer Intern  
**Task:** Identify an AI Opportunity for Cynbit  

**Repository:** https://github.com/Anant8299/project-viva  
**Live demo:** https://cynbit-project-viva.streamlit.app/

## What I built

**Project Viva** is an AI interviewer that asks candidates questions about their own GitHub repo and grades the answers against the actual code. It is meant to serve three parts of Cynbit's business: AI mock interviews in Cynbit Studio, screening after take-home assessments, and end-of-sprint reviews in BitElevate.

## Deliverables

- AI Opportunity Report: `docs/AI_Opportunity_Report.md` (PDF: `docs/AI_Opportunity_Report.pdf`)
- Proof of concept: Streamlit app `app.py`, core package `viva/`
- Technical Approach Report: `docs/Technical_Approach_Report.md` (PDF: `docs/Technical_Approach_Report.pdf`)
- Evaluation: `eval/run_eval.py` and `eval/cases.json`
- Tests: `tests/` (36 tests)

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

- **No API key needed to try it.** In the sidebar, choose "Offline (no API key)", then "Bundled sample (linkshort)", and click Generate questions.
- **LLM mode:** paste a free Groq key (console.groq.com/keys) in the sidebar, or set `LLM_API_KEY`. Then paste any public GitHub repo URL.
- Run the tests with `pytest`, and the grader eval with `python eval/run_eval.py` (add `--llm` and set `LLM_API_KEY` to evaluate the LLM grader).

Python 3.10 or newer.
