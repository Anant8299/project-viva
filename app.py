"""Project Viva - Streamlit demo.

Run:  streamlit run app.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from viva.llm import PROVIDERS, LLMClient
from viva.repo import RepoError, load_from_dir, load_from_github, load_from_zip
from viva.session import build_questions, run_viva

SAMPLE_DIR = Path(__file__).parent / "samples" / "linkshort"
VERDICT_ICON = {"understands": "🟢", "partial": "🟡", "weak": "🔴"}
STATUS_ICON = {"hit": "✅", "partial": "➖", "missed": "❌"}

st.set_page_config(page_title="Project Viva", page_icon="🎙️", layout="wide")


def secret(name: str) -> str:
    try:
        return st.secrets.get(name, "") or os.getenv(name, "")
    except Exception:
        return os.getenv(name, "")


def reset(*keys):
    for k in keys:
        st.session_state.pop(k, None)


# ---------- sidebar ----------
with st.sidebar:
    st.header("Settings")
    mode = st.radio("Engine", ["LLM", "Offline (no API key)"], key="mode", index=0 if secret("LLM_API_KEY") else 1,
                    help="Offline mode uses static analysis templates and keyword grading. "
                         "It is free and deterministic but much less sharp than the LLM.")
    client = None
    if mode == "LLM":
        provider = st.selectbox("Provider", list(PROVIDERS), index=0)
        key = st.text_input("API key", value=secret("LLM_API_KEY"), type="password",
                            help="Groq and Gemini both have free tiers. The key stays in this session.")
        model = st.text_input("Model", value=PROVIDERS[provider]["model"])
        if key:
            client = LLMClient(api_key=key, provider=provider, model=model)
        else:
            st.info("Add a key, or switch to offline mode.")
    n_questions = st.slider("Questions", 3, 8, 5)
    gh_token = st.text_input("GitHub token (optional)", value=secret("GITHUB_TOKEN"), type="password",
                             help="Only needed if you hit GitHub's anonymous rate limit (60 requests/hour).")
    reviewer_view = st.toggle("Reviewer view", value=False,
                              help="Shows the code and expected points next to each question. "
                                   "Keep it off while the candidate is answering.")

st.title("🎙️ Project Viva")
st.caption("Point it at a candidate's repo. It asks questions about their own code, then checks the answers "
           "against the code. Built as a proof of concept for Cynbit Studio's AI mock interviews and "
           "Cynbit's assessment screening.")

# ---------- step 1: source ----------
st.subheader("1. Pick the code")
source = st.radio("Source", ["Public GitHub repo", "Upload ZIP", "Bundled sample (linkshort)"], key="source",
                  horizontal=True, label_visibility="collapsed")
col_a, col_b = st.columns([4, 1])
with col_a:
    url = upload = None
    if source == "Public GitHub repo":
        url = st.text_input("Repo URL", placeholder="https://github.com/owner/repo")
    elif source == "Upload ZIP":
        upload = st.file_uploader("Repo as ZIP (GitHub > Code > Download ZIP)", type=["zip"])
    else:
        st.write("A small URL shortener that ships with this app, so the demo works without network access.")
with col_b:
    st.write("")
    go = st.button("Generate questions", type="primary", use_container_width=True)

if go:
    reset("questions", "report", "warnings", "repo_name")
    try:
        with st.spinner("Reading the repo and writing questions..."):
            if source == "Public GitHub repo":
                if not url:
                    raise RepoError("Paste a repo URL first.")
                files, name = load_from_github(url, token=gh_token or None), url.rstrip("/").split("github.com/")[-1]
            elif source == "Upload ZIP":
                if upload is None:
                    raise RepoError("Upload a ZIP first.")
                files, name = load_from_zip(upload.getvalue()), upload.name.removesuffix(".zip")
            else:
                files, name = load_from_dir(SAMPLE_DIR), "linkshort (sample)"
            questions, warnings = build_questions(files, n_questions, client)
        st.session_state.update(questions=questions, warnings=warnings, repo_name=name, n_files=len(files))
    except RepoError as exc:
        st.error(str(exc))

questions = st.session_state.get("questions")
if questions:
    st.success(f"Read {st.session_state['n_files']} files from **{st.session_state['repo_name']}** "
               f"and wrote {len(questions)} questions.")
    for w in st.session_state.get("warnings", []):
        st.warning(w)

    # ---------- step 2: answers ----------
    st.subheader("2. Candidate answers")
    st.caption("Answer from memory, in your own words. 3-6 sentences each is plenty.")
    with st.form("answers"):
        for q in questions:
            st.markdown(f"**{q.id.upper()}.** {q.question}")
            if reviewer_view:
                with st.expander(f"Code and expected points ({q.kind})"):
                    st.code(q.source, language="python" if q.file.endswith(".py") else None)
                    st.markdown("\n".join(f"- {p}" for p in q.expected_points))
            st.text_area("Answer", key=f"ans_{q.id}", height=110, label_visibility="collapsed")
        submitted = st.form_submit_button("Grade answers", type="primary")

    if submitted:
        answers = {q.id: st.session_state.get(f"ans_{q.id}", "") for q in questions}
        with st.spinner("Grading..."):
            st.session_state["report"] = run_viva(st.session_state["repo_name"], questions, answers, client)

# ---------- step 3: report ----------
report = st.session_state.get("report")
if report:
    st.subheader("3. Report")
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall", f"{report.overall}/100")
    c2.metric("Verdict", f"{VERDICT_ICON[report.band]} {report.band}")
    c3.metric("Questions", len(report.grades))
    for flag in report.red_flags:
        st.error(flag)
    for q, g in zip(report.questions, report.grades):
        with st.expander(f"{VERDICT_ICON[g.verdict]} {q.id.upper()} · `{q.unit_name}` · {g.score}/100"):
            st.markdown(f"> {q.question}")
            for p in g.points:
                ev = f" — _{p.evidence}_" if p.evidence and g.method == "llm" else ""
                st.markdown(f"{STATUS_ICON[p.status]} {p.point}{ev}")
            for e in g.factual_errors:
                st.markdown(f"⚠️ Contradicts the code: {e}")
            if g.flags:
                st.caption("Flags: " + ", ".join(g.flags))
            if g.feedback:
                st.info(g.feedback)
            st.code(q.source, language="python" if q.file.endswith(".py") else None)
    d1, d2 = st.columns(2)
    d1.download_button("Download report (.md)", report.to_markdown(), file_name="viva_report.md")
    d2.download_button(
        "Download raw results (.json)",
        json.dumps({"repo": report.repo, "overall": report.overall, "band": report.band,
                    "questions": [q.to_dict() for q in report.questions],
                    "grades": [g.to_dict() for g in report.grades]}, indent=2),
        file_name="viva_report.json",
    )
