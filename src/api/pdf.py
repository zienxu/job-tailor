"""Render a resume dict to HTML (for preview) and to a PDF via Playwright."""
import io
import tempfile
from pathlib import Path

import pdfplumber
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from src.api.ats import hits

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())
# Default section order = the layout-reference.pdf order. The header always comes first.
ORDER = ["summary", "education", "experience", "leadership", "projects", "skills"]


def render_html(resume: dict, base: str = TEMPLATES.as_uri() + "/") -> str:
    """`base` is where resume.css and fonts/ are served from; an HTTP preview passes its static URL."""
    return _env.get_template("resume.html").render(r=resume, order=resume.get("order") or ORDER, base=base)


def render_pdf(resume: dict) -> bytes:
    """Sync Playwright: call from a plain `def` FastAPI route, not an `async def` one."""
    # The page must live on file:// for Chromium to load the file:// CSS and fonts; about:blank can't.
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        html = Path(tmp) / "resume.html"
        html.write_text(render_html(resume), encoding="utf-8")
        browser = p.chromium.launch(args=["--allow-file-access-from-files"])
        try:
            # No page JS: the page has file access, so injected markup must not be able to run scripts.
            page = browser.new_page(java_script_enabled=False)
            page.goto(html.as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")  # Playwright's evaluate still runs with page JS off
            return page.pdf(prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()


def _rows(resume: dict):
    """(section, role name, row) per role, in display order."""
    for s in resume.get("order") or ORDER:
        if s in ("experience", "projects", "leadership"):
            for r in resume.get(s, []):
                yield s, r.get("company") or r.get("name", ""), r


def _lis(resume: dict) -> list[dict]:
    """Each rendered <li> of a role: one per bullet, one joined line per leadership role (as the template does)."""
    out = []
    for s, role, r in _rows(resume):
        if s != "leadership":
            out += [{"section": s, "role": role, "text": b} for b in r["bullets"]]
        elif r["bullets"]:
            label = role + (f" ({r['role']})" if r["role"] else "")
            out.append({"section": s, "role": role, "text": f"{label}: " + " ".join(r["bullets"])})
    return out


def _shorten(resume: dict, pdf: pdfplumber.PDF) -> list[dict]:
    lines = [l["text"].split() for p in pdf.pages for l in p.extract_text_lines()]
    lis = _lis(resume)
    heads = [li["text"].split()[:5] for li in lis]  # 5 words, so a summary or header line rarely matches a bullet
    starts = lambda line, head: bool(head) and line[:len(head)] == head
    out, cur = [], 0
    for j, li in enumerate(lis):
        words = li["text"].split()
        # A li that can't be found (odd extraction) just gets no suggestion.
        start = next((i for i in range(cur, len(lines)) if starts(lines[i], heads[j])), None)
        if start is None:
            continue
        nxt = heads[j + 1] if j + 1 < len(lis) else []
        end, n = start, len(lines[start])
        # Stop at the next bullet even if merged words left the count short.
        while n < len(words) and end + 1 < len(lines) and not starts(lines[end + 1], nxt):
            end += 1
            n += len(lines[end])
        cur = end + 1
        if end > start:  # only wrapped bullets: trimming a one-line bullet never saves a line
            out.append({**li, "words": len(lines[end])})
    return sorted(out, key=lambda u: u["words"])


def page_fit(resume: dict, pdf_bytes: bytes, fallback: set[str], terms: list[str]) -> dict:
    """Page count plus, when over 1 page, what to shorten (by hand) and then what to remove. Never edits."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = len(pdf.pages)
        if pages <= 1:
            return {"pages": pages, "shorten": [], "remove": []}
        shorten = _shorten(resume, pdf)
    return {"pages": pages, "shorten": shorten, "remove": removal(resume, fallback, terms)}


def removal(resume: dict, fallback: set[str], terms: list[str]) -> list[dict]:
    """Fallback bullets (bottom role first, last-in-role first), then tailored ones with the fewest job-term hits."""
    bottom_up = [{"section": s, "role": role, "text": b} for s, role, r in _rows(resume) for b in r["bullets"]][::-1]
    return ([u for u in bottom_up if u["text"] in fallback]
            + sorted((u for u in bottom_up if u["text"] not in fallback), key=lambda u: hits(terms, u["text"])))
