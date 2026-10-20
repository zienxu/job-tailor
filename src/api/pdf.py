"""Render a resume dict to HTML (for preview) and to a PDF via Playwright."""
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

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
