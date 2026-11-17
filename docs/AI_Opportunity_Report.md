# AI Opportunity Report: Cynbit Technologies

**Prepared for:** Cynbit Technologies, AI/ML Engineer Intern assessment  
**Author:** Anant Pandey  
**Date:** November 2026

## 1. What Cynbit does today

Cynbit is a Jaipur-based engineering studio. From its website and public profiles, the business has four parts:

| Line | What it is | Who pays |
|---|---|---|
| Services | AI automation (LLMs, agents), web and mobile development, AWS/Azure cloud, technical SEO and digital marketing. 13 public case studies across healthcare, fintech, retail, edtech. | Business clients |
| Cynbit Studio | "AI career growth lab": placement assessment, adaptive coding missions, AI code evaluation, AI mentor hints, skill tracking, and career tools (AI mock interviews, resume engine, job matcher). | Students and developers |
| BitElevate | 60-day remote internship. Students work in a Cynbit GitHub repo, open one PR a day, and get line-by-line mentor review. One-time enrollment fee. PPO track for top performers. | Students |
| Revio, TenantEase | SaaS products. Revio is an AI review and reputation engine for multi-location brands. TenantEase is property and tenant management (rent tracking, units, tenant profiles). | Businesses, landlords |

Two things stand out.

First, a large share of Cynbit's work is about **evaluating engineers**: Studio scores code and runs mock interviews, BitElevate reviews daily PRs, and Cynbit hires constantly through take-home assessments like this one. The same skill (judging whether someone can actually do the work) shows up in three places.

Second, that skill is getting harder. Most candidates now write code with AI assistants. Many public submissions to Cynbit's own assessments say so openly in their READMEs. That is fine and often a good sign, but it means a working repo no longer proves the person understands it. A reviewer has to find out, and today the only way is a live conversation with a senior engineer.

## 2. Industry context

**Hiring and edtech.** Take-home assignments became the default screening step because they show real work. AI coding tools have weakened that signal: two candidates can submit similar, polished repos with very different understanding behind them. Companies are responding with follow-up "explain your code" interviews, which are effective but expensive, since they need an engineer's time per candidate.

**Interview practice.** Students preparing for placements mostly practise generic question banks (DSA, OOP, DBMS). The question that trips them up in real interviews is usually about their own project: "why did you do it this way?", "what happens if this fails?". Generic mock interviews don't train that.

**Reputation and PropTech SaaS.** Review management (Revio's space) is mature, with established global players, and sentiment plus reply drafting is now table stakes. Rent-risk prediction (TenantEase) needs real payment history to be useful, which a young product may not have yet.

## 3. Opportunities

I scored each idea from 1 to 5 on four things: business impact, feasibility with data Cynbit has or can easily get, time to first value, and how much it differentiates Cynbit from competitors.

| # | Opportunity | Where | Impact | Feasibility | Time to value | Differentiation | Total |
|---|---|---|---|---|---|---|---|
| 1 | **Project Viva**: AI interviewer that asks candidates about their own repo and checks answers against the code | Studio + hiring + BitElevate | 5 | 5 | 5 | 5 | **20** |
| 2 | First-pass AI review of BitElevate daily PRs, mentor approves | BitElevate | 5 | 4 | 4 | 3 | 16 |
| 3 | Adaptive mission recommendations using knowledge tracing on Studio attempts | Studio | 4 | 3 | 3 | 4 | 14 |
| 4 | Inbound lead triage and first-draft scoping for services inquiries | Services | 4 | 3 | 4 | 2 | 13 |
| 5 | Revio: coordinated fake-review and review-bomb detection across locations | Revio | 4 | 3 | 3 | 3 | 13 |
| 6 | Revio: aspect-level sentiment and crisis escalation | Revio | 3 | 4 | 4 | 1 | 12 |
| 7 | TenantEase: lease and ID document extraction | TenantEase | 3 | 4 | 3 | 2 | 12 |
| 8 | TenantEase: late-payment risk scoring | TenantEase | 4 | 2 | 2 | 3 | 11 |
| 9 | Website assistant grounded in Cynbit's pages | Marketing | 2 | 5 | 5 | 1 | 13 |

Short notes on the ones I did not pick:

- **PR review (#2)** is valuable, but it overlaps with mature tools (GitHub's own review features and several AI review bots). Its real value is cost saving for mentors, not a new capability.
- **Revio sentiment (#6)** is something Revio already advertises. A PoC would mostly re-build an existing feature.
- **TenantEase risk (#8)** needs months of real payment data. On synthetic data any model looks good, which proves little.
- **Website assistant (#9)** is cheap to build but has low impact; Cynbit's site traffic is mostly students and prospective clients who convert through the contact form anyway.

## 4. Selected opportunity: Project Viva

**What it does.** A candidate or student gives a GitHub repo. The system reads the code, picks the functions that carry the most logic, and writes 3 to 8 questions grounded in specific lines: why a check exists, what happens when a call fails, how data moves through a function. The candidate answers in their own words. The system grades each answer against the actual code, point by point, and flags answers that contradict the code.

**Why it is the best fit for Cynbit.**

1. **One engine, three uses.**
   - *Cynbit Studio:* it is the "AI mock interviews" feature, but tied to the student's own projects, which is the part of real interviews students are least prepared for.
   - *Hiring:* after a take-home assessment, every candidate gets an automatic viva. Reviewers spend their time only on candidates who can explain their work.
   - *BitElevate:* at the end of a sprint, interns explain the PRs they shipped. Mentors see who understood the work and who copied it.
2. **It answers the question AI coding tools raised.** Cynbit doesn't need to ban AI assistance. It needs to know whether the person can reason about the code they submit, and this measures that directly.
3. **Uses data Cynbit already has.** Every assessment and every BitElevate intern already produces a GitHub repo. There's no data collection project before it can start.
4. **Low risk.** It never runs candidate code (it only reads it), it doesn't make hiring decisions on its own (it produces a report for a person), and each verdict comes with the evidence behind it.

**Expected value.**

- *Hiring:* a senior engineer's "walk me through your code" call (my estimate: 20-30 minutes per candidate) is replaced, for most candidates, by a 10-minute async viva plus a couple of minutes reading the report. Live calls are kept for the borderline and top candidates. The pilot below would measure the real numbers.
- *Studio:* a feature students would pay for, because it trains exactly the question placement interviewers ask about resume projects.
- *BitElevate:* a stronger certificate. "Passed a viva on their own code" means more to an employer than "submitted 60 PRs".

**How success would be measured in a pilot.**

- Agreement between the viva verdict and a senior engineer's verdict on the same candidates (target: the two agree on most candidates, and the viva never rates a candidate "understands" when the engineer rated them "weak").
- Reviewer time per candidate, before and after.
- For Studio: repeat usage, and whether students who practise score better in later vivas.

## 5. Risks and how the design handles them

| Risk | Mitigation |
|---|---|
| LLM writes a question about behaviour the code doesn't have | Questions are tied to a specific code unit; file and line numbers come from the parser, not the model; expected points are shown to reviewers. |
| Grader is inconsistent or can be talked into high scores | The model labels each expected point (hit / partial / missed); the score is computed in code, never taken from the model. Answers that try to instruct the grader score 0 and are flagged. |
| Candidate looks at the code while answering | Fine for practice. For hiring, the viva is timed and can be followed by a short live check for top candidates. The tool is a filter, not a final decision. |
| Secrets in candidate repos sent to an LLM provider | Obvious keys and passwords are redacted before any API call. A self-hosted model is an option for production. |
| Over-trusting the score | Every report shows the per-point evidence and the code, and verdict bands are worded as "needs a follow-up", not "reject". |

## 6. Recommendation

Build Project Viva as a shared service used by Cynbit Studio, the hiring pipeline and BitElevate. Start with a two-week internal pilot on the next intake of assessment submissions, compare its verdicts against senior engineers' calls, tune the grader on that labelled data, then ship it in Studio as the project-based mock interview.

The proof of concept in this repository covers the core loop end to end. The [Technical Approach Report](Technical_Approach_Report.md) explains how it works and what production would need.
