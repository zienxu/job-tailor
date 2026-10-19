# Decisions

<!-- Format, one entry per decision:
## <date> — <decision>
- Chose: ...
- Rejected: ...
- Why: ...
-->

## 2026-10-19 — Frontend: React (Vite)
- Chose: FastAPI + React (Vite).
- Rejected: FastAPI + server-rendered HTML; Streamlit.
- Why: the editor needs structured fields with flags on each bullet and a live preview; Streamlit is clunky for that.

## 2026-10-19 — PDF engine: Playwright page.pdf()
- Chose: Playwright rendering the same HTML template as the preview.
- Rejected: WeasyPrint (the research default); browser print-to-PDF.
- Why: the PDF must match the preview and the Google Docs layout exactly. Cost: about 150MB of Chromium binaries.

## 2026-10-19 — LLM: Groq free tier, contacts stripped
- Chose: Groq; name, email and phone removed before each call and added back afterwards.
- Rejected: Ollama (weaker at sticking to facts), Gemini/Mistral free tiers (they train on your data), paid Claude API.
- Why: no training and no retention by default, and it's fast. Stripping contacts limits what leaves the machine.

## 2026-10-19 — Fact guard: select and rephrase with source IDs
- Chose: every output bullet cites a bullet or story ID; the app flags bullets with missing or invalid IDs and any number, company or title not in the cited source.
- Rejected: selection only (less tailoring); manual review only.
- Why: invented facts are the biggest non-legal risk. Review in the editor is still required before download.

## 2026-10-19 — Experiences live in the DB, entered through the UI
- Chose: Experience and Stories pages that store data in private/app.db; stories can produce new bullets for the role they're linked to.
- Rejected: Markdown files in private/; one big paste box; LLM extraction from a pasted resume.
- Why: I can update experiences without touching code. One form per role avoids splitting errors and keeps bullet IDs stable.

## 2026-10-19 — Layout reference: dummy-text PDF in docs/
- Chose: docs/layout-reference.pdf, a copy of the Google Doc with placeholder text.
- Rejected: unlocking private/ (all of it, or one file); describing the specs in text; a blurred screenshot.
- Why: Claude can rebuild the exact layout without real personal data entering its context or ending up in commits.

## 2026-10-19 — ATS check: local approximate score
- Chose: keyword coverage against the job, plus a parse test that extracts the text back out of the generated PDF. Both run locally and live in the editor.
- Rejected: third-party checkers such as Jobscan.
- Why: they have no free API, there's a ToS question, and the resume would leave the machine. Real ATS scoring is closed anyway, so any score is an approximation.

## 2026-10-19 — Devil's advocate: suggestion-only critic
- Chose: a second Groq call that runs automatically after tailoring, with a re-run button. It returns suggestions and never edits the text.
- Rejected: an automatic tailor/critic loop; on-demand only.
- Why: I stay in control of every edit and can see the reasoning; it uses fewer calls than a loop.

## 2026-10-19 — Resume font: Carlito over Calibri
- Chose: Carlito (OFL-licensed), bundled as a web font in the resume template.
- Rejected: the real Calibri font (Microsoft-proprietary, not freely redistributable); relying on whatever font is installed on the machine running Playwright.
- Why: Carlito is metric-compatible with Calibri (same character widths/line-wrapping), so the layout-fidelity test against docs/layout-reference.pdf should still hold, and it can be bundled in the repo without a license problem. Resolves the step 3 font/licence blocker.

## 2026-10-19 — Step 1 Groq model and output schema
- Chose: llama-3.3-70b-versatile; each tailored bullet is `{"text": str, "source_id": str}` (one citation id per bullet).
- Rejected: llama-3.1-8b-instant (faster but weaker at respecting citation constraints), openai/gpt-oss-120b (slower); `source_ids: [...]` list form (more flexible but adds validation complexity step 1 doesn't need).
- Why: user picked 70b for reliability over speed; spec's step 1 wording ("cites a bullet or story ID") implies a single id, and the simpler schema is enough for the fail-closed fact-check design.

## 2026-10-19 — Step 2 ATS score: unweighted coverage, no threshold
- Chose: score = matched job terms / all job terms (0-100), every term weighted equally; single-token terms, stopwords removed, whole-token match; always labeled "local estimate".
- Rejected: weighted terms (no basis for weights yet); a pass threshold (spec says never pass/fail); stemming/bigrams (extra code before real data shows a need).
- Why: simplest score that moves when a keyword is added or removed; real ATS scoring is closed anyway.

## 2026-10-19 — Step 2 critic schema
- Chose: same model as step 1; JSON `{unmet_must_haves: [str], weak_bullets: [{text, reason}], missing_keywords: [str], overstated_claims: [{text, reason}]}`; only bullet texts sent (no contacts); bad/mis-shaped response returns empty lists plus `error: "unparseable_response"`.
- Rejected: free-text critique (can't render per category); silently returning partial results.
- Why: matches the four categories in the spec and fails closed like the tailorer.

## 2026-10-19 — Step 3 PDF template details
- Chose: Jinja2 template loaded from a temp file:// page (Chromium blocks file:// CSS/fonts from about:blank); bullets and contact separators drawn as CSS dots; ligatures off; content running past 1 page just fails the test (no auto-trim).
- Rejected: Arial "●" glyphs like the reference (system-font dependency, and they pollute extracted text); inlining fonts as base64 (more code); pixel-diff fallback (2pt text positions were reachable).
- Why: no system font dependency and clean ATS text extraction. Overflow behaviour stays an OPEN spec item. Bold phrases inside bullets (as in the reference) need markup in the data; skipped until the editor (step 7) needs it.

## 2026-10-19 — Step 4 persistence
- Chose: stdlib sqlite3 with CREATE TABLE IF NOT EXISTS; AUTOINCREMENT PKs so a deleted ID is never reused by a new row; DB path overridable via JOB_TAILOR_DB; LLM-facing IDs are prefixed PKs (`role_3`, `bullet_7`, `story_2`); a resume version is a JSON blob of the draft; roles get free-text start/end dates.
- Rejected: SQLAlchemy/migrations (no schema churn yet); storing contacts (deferred until the editor/PDF step needs them, so tailor runs with no contacts); running the critic inside /tailor (critic endpoint comes with the step 7 editor).
- Why: smallest thing that satisfies step 4; PKs never change, so citation IDs stay stable across edits.

## 2026-10-19 — Step 4 review fixes
- Chose: `.env` loaded by `uvicorn --env-file` (python-dotenv); default DB path built from the repo root; tailor() lets LLM call errors propagate and /tailor returns 502 (error type only), while unparseable responses still fail closed; blank text rejected with 422.
- Rejected: load_dotenv() inside main.py (tests importing the app would pull in the real Groq key); a cwd-relative DB path (another start dir silently makes a fresh empty DB); reporting call failures as "unparseable_response" (hides the real cause).
- Why: the documented run command must work, data must not look lost, and the error must say what actually failed.

## 2026-10-19 — Step 5 Experience/Stories UI
- Chose: bullets textarea saved by matching on text (unchanged line keeps its ID, edited line = new bullet, missing line deleted); Vite dev proxy `/api` -> localhost:8000; two tabs via useState; delete buttons, with confirm() before a role delete (cascades its bullets and stories).
- Rejected: matching by line position (inserting a line would move IDs onto different text); CORS in FastAPI (backend change for no gain); react-router (no URLs needed yet).
- Why: a citation must point at the exact text it was fact-checked against; smallest wiring with no backend change.
