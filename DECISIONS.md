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
