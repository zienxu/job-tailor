# job-tailor

A private, localhost-only app that tailors your resume to a job posting, using only facts you have entered yourself. One user, one machine, no login, no hosting.

Paste a job (text, or a link), see how well you fit, tailor a draft, fix what the fact check flags, and download a 1-page PDF in your own layout. Every version is linked to a minimal application tracker.

## What it does
- **Fit grade before tailoring.** A score (1.0 to 5.0), a band (Apply / Stretch / Skip), the must-haves and nice-to-haves you meet or miss, and the saved text that backs each one. The band is advice only and never blocks anything.
- **Fact-checked tailoring.** The LLM rewrites bullets from your saved roles, bullets and stories. Every output bullet must cite a source ID; invented numbers, companies or titles and missing citations are flagged, and a response that doesn't parse flags everything. Name, email and phone never reach the LLM.
- **Live editor.** Per-bullet flags, include checkboxes, section order, a per-job skills line picked from your skills pool, summary templates, and a live preview.
- **Local ATS estimate.** Keyword coverage computed on your machine and always labelled a "local estimate", never a pass/fail verdict.
- **Devil's-advocate critic.** 3 to 5 ranked `{bullet, problem, fix}` suggestions plus a ready / needs-work verdict. It never edits your text.
- **1-page PDF.** Rendered with Playwright from an HTML/CSS template matching `docs/layout-reference.pdf`. Download is blocked until you have reviewed the flags and the page count is 1.
- **Tracker.** Company, role, link, status (saved / applied / interview / offer / rejected), notes, version history, interview prep from the grade, and uploaded PDFs (your own tailored resume or cover letter) per job.

## Stack
FastAPI, React (Vite, Tailwind v4), SQLite, Groq, Playwright (PDF), pdfplumber, pytest, Vitest.

## Setup
You need Python 3.11+, Node, and a [Groq](https://console.groq.com) API key.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium
(cd src/web && npm install)
```

Create a `.env` in the repo root:

```
GROQ_API_KEY=your-key-here
```

## Run
```bash
.venv/bin/uvicorn src.api.main:app --env-file .env       # API, http://localhost:8000
(cd src/web && npm run dev)                               # UI, Vite dev server
```

If port 8000 is already in use, pass `--port` to uvicorn and point the Vite proxy at it.

## Test
```bash
.venv/bin/pytest && (cd src/web && npm test)
```
Tests use fixtures in `tests/fixtures/` and a mocked LLM. They never touch real personal data or call Groq.

## Where things live
| Path | What |
| --- | --- |
| `src/api/` | FastAPI app: `tailor`, `factcheck`, `fit`, `ats`, `critic`, `pdf`, `fetch_job`, `db` |
| `src/api/templates/` | Resume HTML/CSS and bundled Carlito fonts |
| `src/web/src/pages/` | Experience, Stories, Skills, Entries, Editor, Tracker |
| `private/app.db` | Your data (SQLite). Git-ignored |
| `.env` | Your Groq key. Git-ignored |
| `docs/spec.md` | The plan, as numbered testable steps |
| `docs/research.md` | Research behind the choices |
| `DECISIONS.md` | What was chosen, what was rejected, and why |

## Using it
1. **Enter your facts** on the Experience, Projects, Education, Leadership, Skills, Stories and Eligibility pages. This is the only material the tailor may use.
2. **Editor:** paste a job, or a link, then read the grade card.
3. Click **Tailor**, review each flagged bullet, tick or untick what goes on the resume, and check the ATS estimate and critic.
4. **Save a version** or **download the PDF**.
5. Track the application on the **Tracker** page; marking it "applied" records the version you sent.

## Privacy
- Your data stays in `private/app.db`; the only outbound calls are to Groq (contacts stripped first) and to a job link you paste, fetched once.
- Job links: Greenhouse and Lever use their official APIs. Any other https link is read once with an honest user agent, and refused if it is not https, resolves to a private address, or yields too little text. There is no bulk or background scraping.
- Never commit `.env` or `private/`.

## Not in scope
Hosting, login, third-party ATS checkers, generated cover letters (you can upload your own), a kanban board or reminders.
