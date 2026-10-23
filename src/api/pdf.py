"""Render a resume dict to HTML (for preview) and to a PDF via Playwright."""
import io
import re
import tempfile
from pathlib import Path

import pdfplumber
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from playwright.sync_api import sync_playwright

from src.api.ats import hits

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape())


def bold(s) -> Markup:
    """Escape first, then turn **x** into <b>x</b>, so typed markup can never become live HTML."""
    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", str(escape(s))))


EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[A-Za-z]{2,}")
# Domain-like = a scheme, "www.", a /path, or a common TLD, so "Node.js" or "B.Sc" stay plain text.
TLDS = "com|org|net|io|dev|me|sg|co|ai|app|edu|gov|info|page|xyz|tech"
URL_RE = re.compile(rf"https?://\S+|www\.\S+|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{{2,}}/\S*|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:{TLDS})", re.I)
PHONE_RE = re.compile(r"\+?[\d\s().-]{7,}")
YEARS_RE = re.compile(r"(?:19|20)\d\d\s*[-–]\s*(?:19|20)\d\d")  # "2020-2024" is a date range, not a phone


def link(line) -> Markup:
    """One contact line -> mailto:/tel:/https link with the text exactly as typed; anything else stays plain."""
    text = str(line).strip()
    href = None
    if EMAIL_RE.fullmatch(text):
        href = "mailto:" + text
    elif URL_RE.fullmatch(text):
        href = text if re.match(r"https?://", text, re.I) else "https://" + text
    elif PHONE_RE.fullmatch(text) and not YEARS_RE.fullmatch(text) and sum(c.isdigit() for c in text) >= 7:
        href = "tel:" + re.sub(r"[^\d+]", "", text)
    return Markup('<a href="{}">{}</a>').format(href, text) if href else escape(text)


_env.filters.update(bold=bold, link=link)
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
            out += [{"section": s, "role": role, "text": b.replace("**", "")} for b in r["bullets"]]
        elif r["bullets"]:
            label = role + (f" ({r['role']})" if r["role"] else "")
            out.append({"section": s, "role": role, "text": f"{label}: " + " ".join(r["bullets"]).replace("**", "")})
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
            return {"pages": pages, "shorten": [], "remove": [], "drop": []}
        shorten = _shorten(resume, pdf)
    return {"pages": pages, "shorten": shorten, "remove": removal(resume, fallback, terms), "drop": drop_roles(resume, terms)}


def removal(resume: dict, fallback: set[str], terms: list[str]) -> list[dict]:
    """Fallback bullets (bottom role first, last-in-role first), then tailored ones with the fewest job-term hits."""
    bottom_up = [{"section": s, "role": role, "text": b} for s, role, r in _rows(resume) for b in r["bullets"]][::-1]
    return ([u for u in bottom_up if u["text"] in fallback]
            + sorted((u for u in bottom_up if u["text"] not in fallback), key=lambda u: hits(terms, u["text"])))


def drop_roles(resume: dict, terms: list[str]) -> list[dict]:
    """Whole roles, fewest job-term hits first (bottom role first on a tie). Only worth it with 2+ roles."""
    rows = list(_rows(resume))
    if len(rows) < 2:
        return []
    seen: dict[str, int] = {}
    scored = []
    for i, (s, role, r) in enumerate(rows):
        seen[s] = seen.get(s, -1) + 1  # position within its section, so two roles with one name stay apart
        scored.append((hits(terms, " ".join([role, r.get("title") or r.get("role") or "", *r["bullets"]])), -i, s, role, seen[s]))
    return [{"section": s, "role": role, "index": n} for _, _, s, role, n in sorted(scored)]
