# Spec

Stack: FastAPI, React (Vite), SQLite, Groq, Playwright, pdfplumber, pytest, Vitest.

## Problem, user, non-goals
- Problem: a private, localhost-only app. I paste a job (text, or a Greenhouse/Lever link). It tailors my resume using only facts from experiences and stories I enter in the app. It shows a live local ATS score and devil's-advocate critique while I edit, makes a 1-page PDF matching my Google Docs layout, and links each saved version to a minimal job tracker.
- User: me, one person, on my own machine. All personal data lives in private/app.db; the Groq key lives in .env.
- Non-goals: hosting or login, scraping LinkedIn/JobStreet/Indeed/MyCareersFuture, third-party ATS checkers, cover letters, a kanban or reminders, auto-revise loops.

## Demo definition of done
- Paste a real job, get a tailored draft with fact-check flags, fix one bullet, download a 1-page PDF in my Google Docs layout, and see the job in the tracker as "applied" with that version.

## Steps (one per session, riskiest assumption first)
Tests never use real private data or real Groq calls: fixtures in tests/fixtures/ and a mocked LLM. The only exception is the optional manual live run in step 1.

### Feature: Fact-checked tailoring core
1. Tailoring + fact check core, no UI. Roles, bullets and stories with stable IDs go in; name, email and phone are stripped, Groq is called, contacts are added back; every output bullet must cite a bullet or story ID; flags for missing/invalid IDs and for any number, company or title not in the cited source; new bullets may come from a role's own story; fail closed — if a response doesn't parse into valid citations at all, every bullet in it is flagged, none pass silently. Files: src/api/llm.py, src/api/tailor.py, src/api/factcheck.py, tests/fixtures/, tests/test_tailor.py. (test: pytest with mocked LLM on a 10-15 bullet fixture job + resume mixing valid citations, invented numbers, invented companies, and malformed/missing citation IDs: each category is flagged or passed correctly, contacts never reach the LLM call, and an unparseable response flags every bullet; plus one optional manual live Groq run on dummy data.)
REVIEW: code-reviewer on this feature

### Feature: ATS scoring and devil's-advocate critic
2. ATS keyword score + devil's-advocate critic, no UI. Default extraction: a plain term list pulled from the job (not an LLM-tagged must-have/nice-to-have list); score coverage, list missing keywords; wherever the score is shown, it's labeled a "local estimate," never a pass/fail verdict; a second Groq call returns structured suggestions (unmet must-haves, weak bullets, missing keywords, overstated claims) and never edits text. Files: src/api/ats.py, src/api/critic.py, tests/test_ats.py, tests/test_critic.py. (test: pytest on a fixture job + resume: removing a keyword lowers the score and lists it; mocked critic output parses; resume text is identical before and after the critic runs.)
REVIEW: code-reviewer on this feature

### Feature: PDF layout fidelity
3. Layout fidelity + ATS parse test. One HTML/CSS template rebuilt from docs/layout-reference.pdf (fonts, sizes, margins, header spacing, section order), rendered with Playwright page.pdf(); the template bundles Carlito as a web font via @font-face (files under src/api/templates/fonts/), so no system font dependency. Files: src/api/templates/resume.html, src/api/templates/resume.css, src/api/templates/fonts/, src/api/pdf.py, tests/test_pdf.py. (test: pytest renders placeholder content and compares with docs/layout-reference.pdf via pdfplumber: page size, margins, header and section-title positions within about 2pt; output is exactly 1 page; extracted text has name, contacts, standard headings, titles and dates in order with nothing lost. Fallback: if the ~2pt text-position tolerance can't be hit after reasonable effort, fall back to a looser pixel-diff visual comparison instead of exact text-position matching.)
REVIEW: code-reviewer on this feature

### Feature: Backend API and persistence
4. FastAPI + SQLite in private/app.db: tables roles, bullets, stories, jobs, resume_versions; CRUD for experiences and stories, POST /jobs, POST /jobs/{id}/tailor, save version (each save is a new version). Files: src/api/main.py, src/api/db.py, tests/test_api.py. (test: pytest TestClient against a temp DB, LLM mocked: CRUD round-trips, tailor returns flagged draft, two saves make two versions.)
REVIEW: code-reviewer on this feature

### Feature: Experience and Stories UI
5. React Experience and Stories pages: one form per role (company, title, dates, bullets one per line); about 10 stories each linked to a role; editable any time. Files: src/web/src/pages/Experience.tsx, src/web/src/pages/Stories.tsx, src/web/src/api.ts, src/web/src/*.test.tsx. (test: Vitest with mocked API: add a role and a bullet, link a story to a role, save.)
REVIEW: code-reviewer on this feature

### Feature: Design foundation
5b. Design foundation for the currently unstyled web app, reused by steps 7 (Editor) and 8 (Tracker): Tailwind CSS v4 via @tailwindcss/vite, icons via lucide-react, no component library; visual direction from the frontend-design skill, approved by the user from screenshots; light and dark themes follow the system setting (prefers-color-scheme), with colors as CSS variables (design tokens for color, type, spacing); app shell with a collapsible left sidebar listing Experience, Stories, Editor, Tracker, where Editor and Tracker are shown disabled until their steps exist and the collapsed state persists in localStorage (failures ignored); Experience and Stories pages restyled with visible labels unchanged, plus an edit mode: saved roles and stories open read-only with Save and Delete disabled, Edit unlocks them and becomes Cancel (discards changes, or removes an unsaved new item), a successful Save locks the form again while a failed save stays unlocked, and new items from Add role/Add story open unlocked; accessibility: visible focus rings, readable contrast in both themes, aria-current or aria-pressed on the active nav item. Files: src/web/vite.config.ts, src/web/package.json, src/web/tsconfig.json, src/web/src/index.css, src/web/src/main.tsx, src/web/src/App.tsx, src/web/src/pages/Experience.tsx, src/web/src/pages/Stories.tsx, src/web/src/App.test.tsx. (test: Vitest: the existing Experience and Stories tests pass, with an Edit click added where they change a saved item; a saved item is read-only with Save/Delete disabled until Edit, Cancel restores the saved values, Save locks it again, a failed save stays unlocked, and Cancel on a new item removes it; the sidebar collapse toggle works and the collapsed state survives a remount; clicking nav items switches pages; the disabled Editor/Tracker items cannot be activated; npm run build passes; manual sign-off: the user approves screenshots in light and dark mode, sidebar expanded and collapsed.)
REVIEW: code-reviewer on this feature

### Feature: Job link fetch
6. Job link fetch: Greenhouse and Lever official APIs only; any other link is refused with "paste the text". Files: src/api/fetch_job.py, src/api/main.py, tests/test_fetch_job.py. (test: pytest with HTTP mocked: Greenhouse and Lever links return job text; a LinkedIn URL is rejected with "paste the text".)
REVIEW: code-reviewer on this feature

### Feature: Editor UI
7. Editor: structured fields (summary, roles with bullet lists), flags next to each bullet where "missing citation" and "contradicts source" are visually distinguishable from each other, live preview from the step 3 template, live ATS score panel, critic panel with re-run, review required before PDF download. Files: src/web/src/pages/Editor.tsx, src/web/src/components/ScorePanel.tsx, src/web/src/components/CriticPanel.tsx, src/api/main.py, src/web/src/*.test.tsx. (test: Vitest: typing a missing keyword raises the score; a flagged bullet shows its flag with the correct flag-type styling; re-run calls the critic endpoint; download is blocked until review; on the happy-path fixture, no more than about 1 fact-check flag fires on the full resume.)
REVIEW: code-reviewer on this feature

### Feature: Application tracker
8. Tracker: company, role, link, job text, status (saved/applied/interview/offer/rejected), date applied, notes; version history per job; marking "applied" records the version sent; PDFs rebuilt on demand, not stored. Files: src/api/main.py, src/api/db.py, src/web/src/pages/Tracker.tsx, tests/test_tracker.py, src/web/src/*.test.tsx. (test: pytest API sets "applied" with a version id; Vitest list shows status and version.)
REVIEW: code-reviewer on this feature

### Feature: End-to-end demo
9. End-to-end demo with Playwright, Groq mocked, fixture data, temp DB. Files: tests/e2e/demo.spec.ts. (test: Playwright runs the full demo flow above and checks the downloaded PDF is 1 page and the tracker row is "applied" with that version.)
REVIEW: code-reviewer on this feature

## OPEN
- Which Groq model, and the prompt / JSON output schema (tailorer and critic).
- Score weights and the pass threshold for the ATS estimate.
- What happens when content runs past 1 page: warn only, or auto-trim?
- A one-time import of your current resume into the Experience page (manual paste for now?).
- Whether MyCareersFuture's Terms of Use allow fetching (still unchecked).
- Hosting later? (Out of scope now.)
- Filling in the Stack/Run/Test lines in CLAUDE.md once step 3 exists.
- Education, Leadership, Projects and Skills: not in the DB or editor yet, so the PDF has header, summary and Experience only (deferred from step 7).
