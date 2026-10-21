import copy
import io
import json
from pathlib import Path

import pdfplumber
import pytest
from playwright.sync_api import Error as PlaywrightError

from src.api.pdf import link, page_fit, removal, render_html, render_pdf

ROOT = Path(__file__).parent.parent
REFERENCE = ROOT / "docs" / "layout-reference.pdf"
RESUME = json.loads((ROOT / "tests" / "fixtures" / "layout_placeholder.json").read_text())
TOL = 2  # pt
# User choice: margins are half the reference's, so every anchor moves by a known amount.
DY = -4.5  # header top pad 9 -> 4.5
DX_LEFT, DX_RIGHT = -14.4, 21.6  # left margin 28.8 -> 14.4; right text edge 43.2 -> 21.6 from the page edge
CENTRED = {"[Name]", "[Email]", "[Location]"}  # centred over the rules, which stay centred on the page
RIGHT = {"[Graduation Date]", "[End Date]"}

# Anchors whose every occurrence must sit where the reference puts it.
ANCHORS = ["[Name]", "[Email]", "[Location]", "Education", "Experience", "Leadership", "Projects", "Skills",
           "[Graduation Date]", "[Company Name]", "[End Date]", "[Job Title / Role]",
           "[Project Name]", "[Category 1]:", "[Category 3]:", "[Organization / Role]:"]


@pytest.fixture(scope="module")
def pages():
    try:
        out = render_pdf(RESUME)
    except PlaywrightError as e:
        pytest.fail(f"Chromium not available, run `playwright install chromium`: {e}")
    with pdfplumber.open(REFERENCE) as ref, pdfplumber.open(io.BytesIO(out)) as got:
        yield ref.pages, got.pages


def _ink_bbox(page):
    chars = [c for c in page.chars if c["text"].strip()]
    return (min(c["x0"] for c in chars), min(c["top"] for c in chars),
            max(c["x1"] for c in chars), max(c["bottom"] for c in chars))


def test_one_page_same_size(pages):
    ref, got = pages
    assert len(got) == 1
    assert (got[0].width, got[0].height) == (ref[0].width, ref[0].height)


def test_margins_match(pages):
    ref, got = pages
    # Reference bullets are Arial glyphs; ours are drawn, so compare text only.
    no_bullets = lambda c: c.get("text") != "●"
    x0, top, x1, bottom = _ink_bbox(ref[0].filter(no_bullets))
    assert _ink_bbox(got[0]) == pytest.approx((x0 + DX_LEFT, top + DY, x1 + DX_RIGHT, bottom + DY), abs=TOL)


@pytest.mark.parametrize("anchor", ANCHORS)
def test_anchor_positions_match(pages, anchor):
    ref, got = pages
    want = ref[0].search(anchor, regex=False)
    have = got[0].search(anchor, regex=False)
    assert len(have) == len(want) > 0
    dx = 0 if anchor in CENTRED else DX_RIGHT if anchor in RIGHT else DX_LEFT
    for w, h in zip(want, have):
        assert (h["x0"], h["top"], h["x1"]) == pytest.approx((w["x0"] + dx, w["top"] + DY, w["x1"] + dx), abs=TOL)


def test_university_aligns_with_company_at_reference_height(pages):
    ref, got = pages
    uni, company = got[0].search("[University]", regex=False)[0], got[0].search("[Company Name]", regex=False)[0]
    assert uni["x0"] == pytest.approx(company["x0"], abs=0.5)  # user choice: not indented like the reference
    assert uni["top"] == pytest.approx(ref[0].search("[University]", regex=False)[0]["top"] + DY, abs=TOL)


def test_extracted_text_complete_and_in_order(pages):
    _, got = pages
    text = " ".join(got[0].extract_text().split())
    expected = [RESUME["name"], *RESUME["contacts"]]
    expected.append("Education")
    for e in RESUME["education"]:
        expected += [e["school"], e["degree"], e["date"], *e["details"]]
    expected.append("Experience")
    for x in RESUME["experience"]:
        expected += [x["company"], x["dates"], x["title"], *x["bullets"]]
    expected.append("Leadership")
    for l in RESUME["leadership"]:
        expected += [l["name"], *l["bullets"]]
    expected.append("Projects")
    for p in RESUME["projects"]:
        expected += [p["name"], p["dates"], p["role"], *p["bullets"]]
    expected.append("Skills")
    for s in RESUME["skills"]:
        expected += [s["label"], s["text"]]

    pos = 0
    for s in expected:
        found = text.find(s, pos)
        assert found >= 0, f"{s!r} missing or out of order after position {pos}"
        pos = found + len(s)


def test_uses_bundled_carlito(pages):
    _, got = pages
    assert all("Carlito" in c["fontname"] for c in got[0].chars)


def test_long_contact_wraps_instead_of_shrinking_page():
    long = {**RESUME, "contacts": ["https://www.linkedin.com/in/" + "a-very-long-handle-" * 6, *RESUME["contacts"]]}
    with pdfplumber.open(io.BytesIO(render_pdf(long))) as pdf:
        assert len(pdf.pages) == 1
        # Overflow makes Chromium scale the whole page, which shows up as a smaller font size.
        assert pdf.pages[0].chars[0]["size"] == pytest.approx(17, abs=0.1)


def test_html_escapes_content():
    assert "<script>" not in render_html({**RESUME, "name": "<script>x</script>"})


def test_sections_render_in_given_order():
    html = render_html({**RESUME, "summary": "Sum.", "order": ["skills", "projects", "summary", "experience",
                                                                "leadership", "education"]})
    heads = ["Skills", "Projects", "Summary", "Experience", "Leadership", "Education"]
    pos = [html.index(f"<h2>{h}</h2>") for h in heads]
    assert pos == sorted(pos)
    assert html.index("<header>") < pos[0]


LONG = "Built a caching layer for the search service that cut median query latency across every region we serve today"


def test_overflow_reports_two_pages_and_shortens_fewest_last_line_words_first():
    over = copy.deepcopy(RESUME)
    over["experience"][0]["bullets"] += [LONG + " and also the long tail of queries from mobile clients", LONG + " for all of our customers",
                                         *(f"Shipped feature number {i} for the platform team." for i in range(14))]
    over["summary"] = "Built a caching layer once."  # shares 4 leading words; must not be taken for a bullet
    fit = page_fit(over, render_pdf(over), set(), [])
    assert fit["pages"] == 2
    words = [s["words"] for s in fit["shorten"]]
    assert words == sorted(words) and words[0] == 1
    assert fit["shorten"][0]["text"] == LONG + " for all of our customers"
    # One-line bullets can't save a line by trimming, so they are never listed.
    assert not any(s["text"].startswith("Shipped") for s in fit["shorten"])


def test_one_page_has_no_suggestions():
    assert page_fit(RESUME, render_pdf(RESUME), set(), []) == {"pages": 1, "shorten": [], "remove": []}


def test_removal_order_fallback_first_bottom_role_first_then_fewest_hits():
    resume = {"order": ["experience", "leadership", "projects"],
              "experience": [{"company": "Acme", "bullets": ["python go docker", "acme saved 1", "acme saved 2"]}],
              "leadership": [{"name": "Chess", "role": "", "bullets": ["chess saved"]}],
              "projects": [{"name": "Tailor", "role": "", "bullets": ["python", "tailor saved"]}]}
    out = removal(resume, {"acme saved 1", "acme saved 2", "chess saved", "tailor saved"}, ["python", "go", "docker"])
    assert [(u["role"], u["text"]) for u in out] == [
        ("Tailor", "tailor saved"), ("Chess", "chess saved"), ("Acme", "acme saved 2"), ("Acme", "acme saved 1"),
        ("Tailor", "python"), ("Acme", "python go docker")]
    assert all(u["text"] for u in out)  # never a header



def test_bold_marks_up_after_escaping():
    html = render_html({**RESUME, "summary": "A **bold** <script>x</script> and <b>typed</b>",
                        "skills": [{"label": "L", "text": "**s**"}],
                        "leadership": [{"name": "Org", "role": "", "dates": "", "bullets": ["**a**", "b"]}]})
    assert "A <b>bold</b> &lt;script&gt;x&lt;/script&gt; and &lt;b&gt;typed&lt;/b&gt;" in html
    assert "<b>s</b>" in html and "<b>a</b> b" in html


@pytest.mark.parametrize("line,href", [
    ("me@x.com", "mailto:me@x.com"),
    ("+65 9123 4567", "tel:+6591234567"),
    ("linkedin.com/in/me", "https://linkedin.com/in/me"),
    ("http://github.com/me", "http://github.com/me"),
    ("Singapore", None),
    ("www.me.dev", "https://www.me.dev"),
    ("2020-2024", None),
    ("Node.js", None),
    ("B.Sc", None),
    ("javascript:alert(1)", None),
])
def test_contact_links(line, href):
    out = str(link(line))
    assert (f'<a href="{href}">{line}</a>' == out) if href else ("<a" not in out and out == line)


def test_markers_do_not_change_pdf_length():
    marked = {**RESUME, "summary": "**Bold** summary"}
    with pdfplumber.open(io.BytesIO(render_pdf(marked))) as pdf:
        assert len(pdf.pages) == 1
        assert "**" not in pdf.pages[0].extract_text()
