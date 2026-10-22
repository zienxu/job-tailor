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

## 2026-10-20 — Step 7c1 moving roles and entries
- Chose: `POST /{table}/{a}/swap/{b}` (roles, entries) swaps two positions in one commit; a SQLite AFTER INSERT trigger sets `position = id` when none is given; bullets get position through the normal POST/PUT (`Bullet` model).
- Rejected: PUT with a position field for roles/entries (PUT needs the full body, so a move would save unsaved form edits, and two PUTs aren't atomic); setting the initial position in app code (trigger covers every insert path).
- Why: smallest change that keeps moves atomic and leaves the edit flow untouched.

## 2026-10-20 — Step 7c2 keep all roles
- Chose: fallback fill lives in `tailor()` (it already has roles and bullets); a role counts as covered if any LLM bullet cites one of its bullets or stories, flagged or not; an unparseable LLM response gets no fallback.
- Rejected: fallback on unparseable responses (would make a failed call look half-done); doing it in main.py (the role map would be built twice).
- Why: fail closed stays one clear flag; covered = cited matches the spec's "no cited bullet".

## 2026-10-20 — Step 7c2b leadership as roles
- Chose: `_migrate_leadership` in `connect()` moves leadership entries to roles in one `BEGIN IMMEDIATE` transaction (new positions = MAX(roles.position)+i, so they land after existing leadership roles with no ties); one template branch renders Projects and Leadership, hiding the italic line when the role is empty; Position is optional on the Leadership page (migrated rows have none); test_pdf compares anchors from the Projects heading down after subtracting the one shift the taller Leadership rows add, and drops the `[Organization / Role]:` anchor; saved versions no longer store `leadership` (its bullets are in `bullets`, like projects).
- Rejected: keeping the reference's one-line "label: text" Leadership (spec says render like Projects); checking only anchors above Leadership (loses Projects/Skills layout checks); requiring Position (migrated rows couldn't be re-saved); converting old saved versions (spec Open item).
- Why: user's answers in planning; every leadership path then reuses the existing role code with no special cases.

## 2026-10-21 — Step 7c2d best 3 per role
- Chose: flag label "Not in your saved text" (user's choice; a citation can be a story, so "saved bullet" was wrong there); the unparseable bullet gets `included: true`; the Editor treats a missing `included` as true; the Uncited group also gets the include checkbox (unticking takes it out of the review gate, like Remove); unticked textareas stay editable, only muted.
- Rejected: "Not in your saved bullet" (spec draft wording); disabling unticked textareas like copied sections (the tick is a selection, not a lock).
- Why: the review gate must still see any flagged bullet that would reach the user; fewer special cases in the Editor.

## 2026-10-21 — Step 7c3 page fit
- Chose: `/preview` returns JSON `{html, pages, shorten, remove}` and takes optional `job_id` (terms for removal) and `fallback` (texts of included fallback bullets, matched by text); shorten lists wrapped bullets only (a leadership role is one joined line, so one unit), found by matching each li's first words against pdfplumber text lines; the Editor shows the top 5 of each list; the download block is client-side; the Editor waits for both check and preview before opening the gate; `hits` moved to ats.py so tailor and page fit match terms the same way.
- Rejected: all bullets in shorten (trimming a one-line bullet never saves a line); full lists in the UI (too long); a server-side page check on `/pdf` (a second Chromium render per download); per-bullet IDs in the resume payload (text match is enough for a suggestion).
- Why: user's answers in planning; smallest change that keeps the payload shape. Review fixes: bullets are matched on their first 5 words and a wrapped bullet stops at the next bullet's first line; a failed check or preview fails closed (download blocked, retry by editing); `fallback` capped at 500 items.

## 2026-10-21 — No dot before the school name
- Chose: removed the education row's drawn dot (user request); the row keeps its 36pt indent, so text positions are unchanged.
- Rejected: keeping it to match docs/layout-reference.pdf.
- Why: the user doesn't want the university shown as a bullet point.
- Also: the school row is no longer indented, so it lines up with experience company names (user request); test_pdf checks `[University]` against `[Company Name]` x and the reference height instead of the reference x.

## 2026-10-21 — No bottom page margin
- Chose: `@page` bottom margin 0 (was 28.8pt), at the user's request.
- Rejected: adding the same bottom padding to the preview (the user wants the space used).
- Why: the screen preview ignores `@page`, so a resume that filled the preview spilled onto page 2 of the PDF and the page-fit warning disagreed with what the user saw.

## 2026-10-21 — Half margins, margins on body
- Chose: side margins 14.4pt (was 28.8), header top pad 4.5pt (was 9), text stops 7.2pt before the section rules (was 14.4), at the user's request; margins moved from `@page` to body padding so the screen preview and the PDF wrap at the same width; test_pdf expects the reference positions shifted by those amounts.
- Rejected: halving only `@page` (the preview would still have no margins and wrap wider than the PDF).
- Why: before this, the preview ignored `@page`, so its lines were 57.6pt wider than the PDF's and the page-fit count disagreed with it.

## 2026-10-21 — 7c4 scoring details
- Chose: a line whose text before any ":" is at most 5 words and names a known section sets the weight, and the rest of the line still gives terms ("Requirements: Kubernetes", "Must have Python"), only the heading words are dropped; Preferred/Nice to have is checked before Requirements/Qualifications ("Preferred qualifications" = 1); any other short line ending in ":" that is not a bullet (e.g. "Responsibilities:") resets the weight to 1 and is not a term; a term seen under several headings keeps its highest weight; 2-word phrases never span `, ; : ( )`, a line break or ". "; only purely alphabetic tokens are stemmed (c++, ci/cd, node.js stay whole); per-role hits are unweighted distinct-term counts over company, title and included bullets, via a `roles` map on `/check` (main.py and api.ts changed though not listed in the step).
- Rejected: weight 2 running to the end of the job once a Requirements heading appears (Responsibilities after it would count double); pairs across commas ("Python, SQL" as a phrase); computing per-role hits in the browser (would duplicate the stemmer in TS).
- Why: the spec fixes the weights but not where a section ends or what a phrase boundary is; these are the smallest rules that keep list items from becoming junk phrases.
- 7d: bold filter escapes before turning **x** into <b>; the B button uses setRangeText + a dispatched input event so existing onChange handlers work unchanged (rejected: a controlled value/onChange(string) prop, which would change every caller). Critic input keeps markers (the spec strips them only for ATS and fact check).
- 7d review: contact links need a scheme, www., a /path or a common TLD (so Node.js/B.Sc stay plain) and year ranges are not phones; Bold uses execCommand('insertText') for undo, falling back to setRangeText + input event.

## 2026-10-21 — Step 8 tracker
- Chose: each saved version also stores `resume` (the exact payload sent to /pdf); `GET /versions/{id}/pdf` re-renders it and returns 409 for versions saved before step 8; the tracker lists every job with a Delete button (versions cascade); `jobs.version_id` has no FK, `PUT /jobs/{id}` checks the version belongs to the job and that "applied" has one; choosing "applied" pre-fills the newest version and today's local date; plain forms, no 5b edit mode; Editor.tsx changed (one line) though not listed in the step.
- Rejected: rebuilding from the draft + current role headers (renaming a role would change old PDFs); hiding jobs with no versions (user chose list all + Delete); an FK on version_id (cycle with the job's cascade delete).
- Why: user's answers in planning; the rebuilt PDF is the version sent.
- Step 8 review: a stored `resume` that fails the Resume model gives 409 on rebuild (not 500, and save stays unvalidated so old drafts still save); `applied_at` must be '' or YYYY-MM-DD; version times shown in local time (SQLite stores UTC); Save is disabled per card.
- Step 8 follow-up: Download PDF no longer saves a version; only the Editor's "Save in tracker" button does, behind the same gate as download (user's choice); `GET /jobs` lists only jobs with a saved version (Tailor still makes a job row because /check, /critique and /preview need a job id); the Tracker is a table with inline inputs per row and an expandable detail row for notes, versions and job text. Rejected: creating the job row only on save (every Editor endpoint takes a job id); a read-only table with an Edit button (user picked inline).
- Tracker numbering: the # column is the row's place among saved jobs (oldest = 1), and the Editor's save message uses the same number (it re-lists jobs after saving); `POST /jobs` first deletes jobs with no saved version, so unsaved Tailor runs don't pile up. Rejected: resetting or reusing job ids after a delete (versions link by id, AUTOINCREMENT never reuses, and a reused number could point an old reference at a different job).

## 2026-10-21 — Fit grade before tailoring (spec 8b–8e)
- Chose: a pre-tailor fit grade from the full saved profile (education included) where the LLM lists requirements (must/nice, hard gate, met/partial/missing, evidence IDs) and code scores them (must 2, nice 1, met 1, partial ½; score = 1 + 4 × coverage); bands Apply ≥ 3.8, Stretch 3.0–3.7, Skip < 3.0, a missing hard gate caps at Stretch; advice only, Tailor always enabled. Reference: career-ops modes/_shared.md @ c87e0f0 (MIT).
- Rejected: career-ops' 4.0 apply cutoff (would skip roles a ~70% match can realistically get); an LLM-decided 1–5 score (drifts between runs, can't be checked against saved IDs); preferences dimensions like salary/location (need a new page, user chose experience match only); using career-ops itself (no API, markdown-only output, no fact check).
- ATS (8d): reverses step 2's "not an LLM-tagged list" rule; graded jobs score against the grade's 10–25 must/nice keywords, still matched locally. Why: counting every non-stopword in the ad (about-us, benefits) kept scores at 20–30% for good resumes.
- Critic (8e): 3 to 5 {bullet, problem, fix} items (user's choice; extras are cut to the first 5, not rejected), sees each bullet's cited source text; unmet_must_haves and missing_keywords dropped (the grade and ATS panel cover them). Why: the uncapped skeptical critic flagged true claims it could not check.

## 2026-10-22 — Step 8b fit grade backend
- Chose: valid evidence IDs are role, bullet, story and skill IDs (role IDs so a degree, i.e. an education role's school + degree, can be cited); IDs not in the profile are dropped, and a met/partial left with none becomes missing; the 10–25 keyword count is asked in the prompt, not enforced (only the shape is checked); a failed grade (LLM error, bad JSON, wrong shape, empty requirements) returns HTTP 502 and stores nothing, like /tailor; `load_profile(conn, full=True)` gives the grade profile (all role kinds with kind, plus skills) so the tailor's call is unchanged; GET /jobs/{id} returns `grade` decoded (null when ungraded).
- Rejected: the critic's 200 + `error` key (the UI already handles /tailor's 502s); rejecting responses with fewer than 10 or more than 25 keywords (a good grade would be thrown away over a count).
- Why: user approved these in planning; the spec fixes the scoring, not these edges.
- 8b review: the score rounds half-up (3.25 -> 3.3) via Decimal, not Python's half-even round() (3.25 -> 3.2), so a score exactly between two tenths is never pulled down a band; every job route (POST/GET/PUT /jobs, GET /jobs) returns `grade` decoded through one `_job()` helper.

## 2026-10-22 — Step 8c grade UI
- Chose: a "Grade fit" button (and Fetch on a Greenhouse/Lever link) creates the job and grades it; Tailor reuses that job while the text is unchanged (a new POST /jobs deletes unsaved jobs) and is never gated on the band or a failed grade; POST /jobs/{id}/grade stores each requirement's cited saved text as `evidence`, a snapshot at grade time that Re-grade refreshes; "reopening" a job = the Tracker detail row shows the stored grade (from GET /jobs, no new call) and a Fit column shows the band, blank when ungraded.
- Rejected: auto-grading on paste (an LLM call per paste, and typed text would need a button anyway); resolving evidence IDs on every read (a profile load per job listing); an "Open in Editor" path (needs app-level page and job state, not in the spec).
- 8c review: the unsaved-job cleanup moved from POST /jobs to a successful /jobs/{id}/tailor (it deletes other unsaved jobs), so grading a new job text never deletes the draft being edited; the editor then treats the tailored job as the graded one. A fetched link's company/title/link are dropped once the job text or link is edited by hand, so a pasted job never inherits another job's link. Rejected: keeping the cleanup in POST /jobs with an "except this id" parameter (the client would have to track which job is live).

## 2026-10-22 — Step 8c2 any job link
- Chose (user's call, accepting the ToS risk research.md records for LinkedIn, JobStreet and Indeed): /jobs/fetch reads any single pasted https link once; Greenhouse/Lever still use their official APIs; other pages are read from their schema.org JobPosting JSON-LD, else their visible text (the user trims it); honest user agent, no block bypassing, so a login wall or HTTP 999 just says "paste the text"; https only, and hosts (and redirect targets) must resolve to public addresses, since the server now fetches arbitrary URLs.
- Rejected: a browser-like user agent or headless Playwright to get past bot walls (that is evading the site's blocks); per-site HTML selectors (break on every redesign; JSON-LD is what sites publish for search engines); fetching without the private-address check (a pasted link could make the server hit localhost:8000 or the LAN).

## 2026-10-22 — Step 8c3 eligibility facts and band legend
- Chose: a grade-only Eligibility page (entries section "eligibility") for facts the resume never states but jobs gate on (citizenship/PR, start date, experience level); they reach the grade as citable fact_N IDs, never the tailor, Editor or PDF; the grade card shows the band thresholds and names the missing hard requirement when it held a >= 3.8 score at Stretch.
- Rejected: a Skills entry (prints on the resume by default); feeding facts to the tailor (it could turn "Singapore Citizen" into a bullet); computing experience years from role dates (the stated fact is clearer than parsing free-text dates).
- 8c2/8c3 review: the page fetch also refuses IPv4-mapped and NAT64 (64:ff9b::/96) addresses, which Python's is_global lets through; odd JSON-LD (@graph null or a dict), an unknown charset and an empty description no longer crash or return empty text; fetched text is capped at 50,000 characters; an entry can't change section via PUT, so an eligibility fact can never be moved into resume skills.

## 2026-10-22 — Step 8f grade nuance
- Chose: keep the 1-5 decimal and the formula; add seniority_fit (under/match/over) and a one-sentence summary from the same Groq call, advice only; any missing must-have (not only a hard gate) caps Apply at Stretch.
- Rejected: hiding the decimal behind bands only (user wants to see it and tune later); a holistic-only band with no formula (loses the evidence-ID trail); folding seniority into the score (no basis for a weight yet); a separate second LLM call for the summary (cost, and it could disagree with the requirements).
- Why: research found the checklist misses seniority and treats a missing must like a small dent; the 3.8/3.0 cut-offs stay a guess until about 10 real jobs. Old stored grades lack the two new fields, so the UI treats them as optional.

## 2026-10-22 — Step 8d ATS uses grade keywords
- Chose (reverses step 2's "not an LLM-tagged list" and 7c4's heading weights, for graded jobs only): a graded job's ATS score, per-role hits, 7c2d bullet ranking and 7c3 removal order all use the grade's stored keywords, must 2 and nice 1, matched locally with the same stemming; an ungraded job keeps `_terms()` unchanged. `_keys()` now also emits 3-4 word stem runs so multi-word keywords like "large language models" can match (5+ words never match).
- Rejected: `_terms()` for every job (every non-stopword counts, so real jobs sit at 20-30%); an LLM-decided score (not local, not repeatable); the union of grade keywords and `_terms()` (the noise terms pull the score back down); an LLM call at check time (the keywords are already stored with the grade).

## 2026-10-22 — Step 8g story bullets in one sentence
- Chose (user's call): a bullet citing a story must be one resume sentence of at most 30 words; the prompt asks for it and check_bullet flags anything longer as story_too_long, so it goes through the review gate like any other flag; a sentence break is end punctuation followed by a capital, so "e.g. caching" stays one sentence; a fact flag wins over the length flag; bullets citing saved bullets are never length-checked (that text is the user's own).
- Rejected: dropping stories from the tailor (loses new bullets from stories); a prompt-only change (the LLM was already copying whole stories); auto-trimming the text in code (it would edit the user's facts silently).
- 8d/8g review: a malformed stored grade keyword (no string term, not a dict) is skipped instead of raising a 500, and a grade with no usable keywords falls back to the job's own terms; a missing kind counts as nice; a stored grade that is not a dict counts as ungraded; /preview reads the job row once; the sentence-break limit ("U.S. Army") is marked as a shortcut.
