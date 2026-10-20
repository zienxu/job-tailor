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

## 2026-10-19 — Step 6 job link fetch
- Chose: stdlib urllib; POST /jobs/fetch returns {text, title, company, link} without saving (UI then calls POST /jobs); exact-host allowlist (boards/job-boards[.eu].greenhouse.io, jobs[.eu].lever.co), https only, path segments regex-checked before building the API URL; job HTML turned into text with a small regex strip; refusal = 422 "paste the text", upstream failure = 502 (error type only).
- Rejected: httpx/requests as a runtime dependency (httpx is dev-only); fetch-and-save in one call (nothing should be stored before the user confirms); substring host checks (look-alike hosts); BeautifulSoup (new dependency for a few tags); Greenhouse `?gh_jid=` embeds on company sites and Workday (not official FETCH OK sources).
- Why: spec allows only the official Greenhouse/Lever APIs, and a server-side fetch must never be steered at another host.

## 2026-10-20 — Step 5b design foundation (planned)
- Chose: Tailwind CSS v4 via @tailwindcss/vite, lucide-react icons, light/dark from prefers-color-scheme with CSS-variable tokens; collapsible left sidebar for all 4 pages (Editor/Tracker disabled until built); done now as its own step 5b, not at the end of the project.
- Rejected: a component library (shadcn/Mantine: most dependencies, and the look comes from design choices, not the library); plain CSS (fine, but slower to iterate on the look); a slim top bar (user preferred a sidebar); amending step 5 (it is already committed as done); pixel-snapshot tests (break on every intentional tweak, so screenshots get manual sign-off instead).
- Why: steps 7 and 8 reuse the tokens and shell, so settling them before more UI exists avoids restyling three times; unchanged labels keep the step 5 tests valid.

## 2026-10-20 — Step 5b design foundation (built)
- Chose: fonts bundled with @fontsource-variable (Public Sans for app chrome, Source Serif 4 for your own words: bullets, stories, headings) so it works offline; colors as CSS variables swapped by prefers-color-scheme and mapped into Tailwind with `@theme inline` (no `dark:` classes needed); shared `.field/.btn/.record` classes in index.css for steps 7 and 8; ruled bullets box; sidebar is an icon rail below 640px; `vite/client` added to tsconfig types so the CSS import type-checks; new packages pinned exactly like the existing ones.
- Rejected: Google Fonts CDN (needs network on a localhost tool); system fonts only (look differs per machine); `dark:` variants on every class (doubles every color class); per-line bullet chips (would change the textarea logic step 5 tests rely on).
- Spacing tokens: Tailwind's default 4px scale is the spacing token set; no custom scale.
- Why: one token set drives both themes; steps 7 and 8 restyle nothing, they just reuse the classes.

## 2026-10-20 — Step 5b edit mode (user request)
- Chose: per-form `editing` flag plus an `orig` snapshot taken when Edit is clicked; inputs/textareas use readOnly (still selectable and copyable), the role select uses disabled (selects have no read-only state); Save and Delete stay visible but disabled while locked; Cancel restores the snapshot, or removes a never-saved item; Save locks only on full success.
- Rejected: hiding the fields behind a separate view layout (two renderings of the same data to keep in sync); a page-wide edit mode (one Edit unlocking every role invites accidental edits to the others).
- Why: the user wants saved facts protected from accidental edits, since the tailor cites them by ID and an edited bullet line becomes a new bullet.

## 2026-10-20 — Step 7 editor
- Chose: one debounced `POST /jobs/{id}/check` that returns the ATS score and re-runs the fact check per bullet, so a fixed bullet loses its flag; `/tailor` adds each bullet's `role_id` from its cited source so the editor can group by role; name and contacts saved inside each version's JSON and pre-filled from `GET /versions/latest`; summary in the PDF only when not empty; review gate = every flag fixed, removed or marked "Keep anyway", plus an "I've reviewed this draft" tick that any edit clears; download saves a version first; uncited bullets are shown but left out of the PDF; preview in an `<iframe sandbox="allow-same-origin">` (no scripts) with template CSS/fonts served at /templates; flag kinds: `unsupported_fact` = "Contradicts source" (red), every citation problem = "Missing citation" (amber).
- Rejected: porting ats.py to TypeScript (two scorers to keep in sync); a contacts table (versions already store the draft); a checkbox-only gate (lets flagged bullets through); sandbox without same-origin (opaque origin blocks the web fonts).
- Tests: the spec's "about 1 flag on the happy-path fixture" check is in pytest (tests/test_editor_api.py), not Vitest, because only the real check_bullet makes it meaningful.
- Skipped: job-link fetch UI (endpoint exists, paste is enough for the demo); editing company/title in the editor (use Experience); Education/Leadership/Projects/Skills (OPEN).
- Why: user's answers in planning; one implementation of each check.

## 2026-10-20 — Step 7 review fixes
- Chose: download also waits until the fact check of the latest edit has returned; `/preview` and `/pdf` take a typed Resume model; 422 responses list only loc/msg/type, never the request body; a critic result from an older tailor run is dropped; the PDF blob URL is revoked after the click finishes.
- Rejected: "Present" for a role with no end date (not in the spec, so left for the user); "Keep anyway" on uncited bullets (they never reach the PDF).
- Why: code-reviewer findings: flags from an older draft could pass the gate, and FastAPI's default 422 echoed contacts into the on-screen error.

## 2026-10-20 — Steps 7b–7d resume sections, bold, links (planned)
- Chose: projects and education as roles with a `kind` column (education never sent to the tailor); leadership/skills in an `entries` table as label + text, copied verbatim with a per-draft include tick and editable text; project bullets tailored and fact-checked like experience; section order set with up/down buttons in the Editor, saved in each version and pre-filled from the latest; bold as `**word**` with a B button / Ctrl+B, rendered after escaping, stripped for ATS and fact check, kept by the tailor; contacts auto-linked (mailto/tel/https), styled as plain text.
- Rejected: rich-text editing (breaks the line-matched bullet textarea that keeps citation IDs, new dependency, test churn); a separate projects table (duplicates role CRUD, citations, fact check); LLM-tailored leadership/skills; a global section-order setting; per-draft-only order; "Text | URL" contact syntax; blue underlined links.
- Why: user's answers in planning; reuse the existing role/citation path instead of a parallel one.

## 2026-10-20 — Step 7b data + entry pages (built)
- Chose: `kind` migration runs in `connect()` (PRAGMA table_info check, then ALTER TABLE); `Role.kind` and `Entry.section` are Pydantic Literals, so bad values get a 422 and the DB has no CHECK; entry label and text are both required; `load_profile` also drops bullets/stories whose role is education; the Stories role picker hides education roles; Experience/Projects/Education share one page through a per-kind label table; Entries.tsx copies the Stories edit-mode structure.
- Rejected: a migrations framework (one column); a shared record-form component (three pages with small differences, harder to read than the copies); filtering by kind on the server (`GET /roles` stays generic, the pages filter).
- Note: `PUT /roles` without `kind` resets it to experience; the UI always sends it.
- Until 7c, tailored project bullets show in the Editor under their project like any role.
- Why: the smallest change that keeps every existing role, citation and test path working.
- Review fixes: `PUT` now writes only the fields sent (`exclude_unset`), so leaving out `kind` keeps it instead of resetting to experience (replaces the note above); the migration ignores "duplicate column" when two connections race; the Stories picker still shows an education role for a story already linked to it.

## 2026-10-20 — Step 7c editor sections + order (built)
- Chose: default order = layout-reference.pdf order (summary, education, experience, leadership, projects, skills), not the spec's listed order with projects before leadership, so the step 3 layout test stays valid; `order` is a Literal list on the Resume model (unknown section = 422) and `render_html` falls back to the default when a dict has none; leadership/skills labels render as `label:` with any trailing colon the user typed stripped first; education's per-draft edit is the detail lines only (school/degree/dates edited on the Education page); each version stores `order` plus the education/leadership/skills as sent, so step 8 can rebuild that PDF, but only `order` is pre-filled from the latest version.
- Rejected: one Jinja include file per section (six files for six short blocks); a separate draft table for the copied sections (version JSON already holds the draft).
- Why: user's answers in planning.

## 2026-10-20 — Steps 7c1-7c4 keep all roles, page fit, scoring (planned)
- Chose: 7c1 up/down order on Experience, Projects, Leadership, Skills pages, saved as a `position` column (education keeps creation order); bullet order follows textarea line order, IDs still matched by text. 7c2 the prompt groups sources by role and asks for at least 1 bullet per experience/project role; `/tailor` fills any role still uncovered with its first 2 saved bullets, verbatim, cited by their own ID, `fallback: true`, normal fact check, "Copied as saved" note; a role with no saved bullets shows its header line only. 7c3 `/preview` returns the Playwright page count; over 1 page = warning + suggestions and download blocked; suggest shortening first (bullets with the fewest words on their last line, measured with pdfplumber, edited by hand), then removal (fallback bullets 2->1 from the bottom-most role, then tailored bullets with the fewest job-term hits, never a role header). 7c4 snowballstemmer stemming; 2-word job phrases count only if repeated in the job; terms under Requirements/Must have/Qualifications headings weigh 2, Preferred/Nice to have 1, no headings = all 1; whole-resume % plus per-role hit counts; breadth not scored; the critic adds `readiness {verdict, reason}` in the same call, advice only.
- Rejected: prompt-only (LLM still skips) and Editor-only fallback (not in saved versions, not pytest-testable); header-only skipped roles; 1 or all saved bullets; LLM or keyword picking of fallback bullets; skipping the fact check for fallback bullets (same result, extra state); auto-trim (silently drops content); 2-page download; iframe-height page detection (can drift from the PDF); an LLM Shorten button (new fact-check risk); longest-by-characters suggestions (may save no line); plain tokens or a crude suffix strip; BM25/TF-IDF (rank many documents, not one-vs-one coverage); local embeddings (torch ~150MB+, slow per keystroke); breadth inside the score (no evidence ATS reward it); per-section %; a separate readiness LLM call; a verdict that gates download; every-pair bigrams (junk terms); parsing end years from free-text dates; reordering per draft or in the Editor; reordering education.
- Why: user's answers in planning, backed by the 2026-10-20 research block (no evidence for location/recency weighting or density penalties; 1-2 bullets for less relevant roles is common advice). Fallback in `/tailor` keeps one code path, and verbatim bullets already pass `check_bullet`.
