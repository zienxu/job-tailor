import json
from pathlib import Path

from src.api.ats import extract_terms, score

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE = json.loads((FIXTURES / "profile.json").read_text())
JOB_TEXT = (FIXTURES / "job.txt").read_text()
RESUME_TEXT = "\n".join(b["text"] for b in PROFILE["bullets"])


def test_removing_a_keyword_lowers_score_and_lists_it():
    full = score(JOB_TEXT, RESUME_TEXT)
    assert "postgresql" in full["matched"]

    without = score(JOB_TEXT, RESUME_TEXT.replace("PostgreSQL", ""))
    assert without["score"] < full["score"]
    assert "postgresql" in without["missing"]


def test_labeled_local_estimate_never_pass_fail():
    result = score(JOB_TEXT, RESUME_TEXT)
    assert result["label"] == "local estimate"
    assert set(result) == {"label", "score", "matched", "missing"}


def test_extract_terms_is_plain_list_keeping_tech_tokens():
    terms = extract_terms(JOB_TEXT)
    assert "ci/cd" in terms
    assert "cross-team" in terms
    assert "the" not in terms and "and" not in terms
    assert len(terms) == len(set(terms))


def test_numbers_and_abbreviations_are_not_keywords():
    assert extract_terms("5+ years, e.g. 10 engineers using C++") == ["engineers", "c++"]


def test_whole_token_match_not_substring():
    assert score("Go developer", "Good developer")["missing"] == ["go"]
