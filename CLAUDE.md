# job-tailor
Stack: FastAPI, React (Vite), SQLite, Groq, Playwright (PDF), pdfplumber, pytest, Vitest
Run: .venv/bin/uvicorn src.api.main:app --env-file .env  +  (cd src/web && npm run dev)
Test: .venv/bin/pytest && (cd src/web && npm test)
First time: pip install -e ".[dev]" && playwright install chromium && (cd src/web && npm install)

Rules
- Read docs/spec.md first, then docs/research.md. Do ONE numbered step per request, then stop.
- A step is done only when its tests pass. Use the test-runner agent to run them.
- Secrets live in .env only. Personal data lives in private/ only. Never read, print or commit either.
- If a decision is not in docs/spec.md, ask. Do not invent it.
- Log non-obvious choices in DECISIONS.md (what, what was rejected, why).
- Keep this file under 60 lines. Project detail belongs in docs/.

Agents (.claude/agents/)
- researcher: unknown APIs, libraries, limits. Cheap model, read-only.
- spec-writer: idea -> docs/spec.md. Writes only in docs/.
- test-runner: after every step. Cheap model, reports failures only.
- code-reviewer: end of each feature. Read-only.
- bug-hunter: before a demo or after a risky feature. Writes only in tests/.
