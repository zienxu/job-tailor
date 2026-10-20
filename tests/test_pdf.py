import io
import json
from pathlib import Path

import pdfplumber
import pytest
from playwright.sync_api import Error as PlaywrightError

from src.api.pdf import render_html, render_pdf

ROOT = Path(__file__).parent.parent
REFERENCE = ROOT / "docs" / "layout-reference.pdf"
RESUME = json.loads((ROOT / "tests" / "fixtures" / "layout_placeholder.json").read_text())
TOL = 2  # pt

# Anchors whose every occurrence must sit where the reference puts it.
ANCHORS = ["[Name]", "[Email]", "[Location]", "Education", "Experience", "Leadership", "Projects", "Skills",
           "[University]", "[Graduation Date]", "[Company Name]", "[End Date]", "[Job Title / Role]",
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
    for r, g in zip(_ink_bbox(ref[0].filter(no_bullets)), _ink_bbox(got[0])):
        assert g == pytest.approx(r, abs=TOL)


@pytest.mark.parametrize("anchor", ANCHORS)
def test_anchor_positions_match(pages, anchor):
    ref, got = pages
    want = ref[0].search(anchor, regex=False)
    have = got[0].search(anchor, regex=False)
    assert len(have) == len(want) > 0
    for w, h in zip(want, have):
        assert (h["x0"], h["top"], h["x1"]) == pytest.approx((w["x0"], w["top"], w["x1"]), abs=TOL)


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
