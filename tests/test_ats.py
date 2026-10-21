import json
from pathlib import Path

from src.api.ats import extract_terms, hits, score

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


def test_stemming_matches_word_forms():
    assert score("Mentor junior engineers", "Mentored a junior engineer")["missing"] == []


def test_repeated_bigram_is_a_term_and_once_only_pair_is_not():
    job = "Machine learning models.\nYou will ship machine learning to prod. Data pipelines."
    terms = extract_terms(job)
    assert "machine learning" in terms
    assert "data pipelines" not in terms
    assert "machine learning" in score(job, "machine and learning")["missing"]
    assert "machine learning" in score(job, "Built machine learning systems")["matched"]


def test_required_terms_weigh_more_than_preferred():
    job = "About us\nWe build things.\n\nRequirements:\n- Kubernetes\n\nPreferred qualifications\n- Terraform"
    full = "build things kubernetes terraform"
    no_required = score(job, full.replace("kubernetes", ""))["score"]
    no_preferred = score(job, full.replace("terraform", ""))["score"]
    assert no_required < no_preferred < score(job, full)["score"]


def test_per_role_hits():
    terms = extract_terms(JOB_TEXT)
    assert hits(terms, "Mentored engineers on PostgreSQL") == 3  # mentor, engineers, postgresql
    assert hits(terms, "Baked bread") == 0


def test_inline_headings_keep_their_terms_and_set_weight():
    job = "Must have Python\nPreferred: Terraform, AWS\nRequirements: Kubernetes\n- Strong communication skills:"
    terms = extract_terms(job)
    assert {"python", "terraform", "aws", "kubernetes", "communication"} <= set(terms)
    assert not {"requirements", "preferred"} & set(terms)
    full = "python terraform aws kubernetes communication"
    assert score(job, full.replace("kubernetes", ""))["score"] < score(job, full.replace("aws", ""))["score"]
