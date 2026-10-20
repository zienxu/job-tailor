import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.api.tailor import tailor
from src.api.factcheck import check_bullet

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE = json.loads((FIXTURES / "profile.json").read_text())
JOB_TEXT = (FIXTURES / "job.txt").read_text()


def mock_response(bullets):
    return json.dumps({"bullets": bullets})


def test_valid_citation_passes_with_no_flags():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Led a team of 5 engineers to ship the checkout redesign at Acme Corp.",
         "source_id": "bullet_1"},
    ])):
        result = tailor(JOB_TEXT, PROFILE)
    assert result["bullets"][0]["flags"] == []


def test_invented_number_is_flagged():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Reduced page load time by 90% through caching improvements.",
         "source_id": "bullet_2"},
    ])):
        result = tailor(JOB_TEXT, PROFILE)
    assert result["bullets"][0]["flags"] == ["unsupported_fact"]


def test_invented_company_is_flagged():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Mentored 2 junior engineers as a Senior Developer at Initech.",
         "source_id": "bullet_4"},
    ])):
        result = tailor(JOB_TEXT, PROFILE)
    assert result["bullets"][0]["flags"] == ["unsupported_fact"]


def test_invalid_citation_id_is_flagged():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Migrated the database from MySQL to PostgreSQL with zero downtime.",
         "source_id": "bogus_id"},
    ])):
        result = tailor(JOB_TEXT, PROFILE)
    assert result["bullets"][0]["flags"] == ["invalid_citation_id"]


def test_missing_source_id_is_flagged():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Cut deployment time significantly."},
    ])):
        result = tailor(JOB_TEXT, PROFILE)
    assert result["bullets"][0]["flags"] == ["missing_citation"]


def test_unparseable_response_flags_everything():
    with patch("src.api.tailor.llm.complete", return_value="not valid json at all"):
        result = tailor(JOB_TEXT, PROFILE)
    assert len(result["bullets"]) == 1
    assert result["bullets"][0]["flags"] == ["unparseable_response"]


def test_new_bullet_from_story_cites_story_id():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Resolved a critical production outage affecting 10000 users within 30 minutes.",
         "source_id": "story_1"},
    ])):
        result = tailor(JOB_TEXT, PROFILE)
    assert result["bullets"][0]["flags"] == []


def test_contacts_never_reach_the_llm_call():
    captured = {}

    def fake_complete(system_prompt, user_prompt):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return mock_response([])

    with patch("src.api.tailor.llm.complete", side_effect=fake_complete):
        result = tailor(JOB_TEXT, PROFILE)

    contacts = PROFILE["contacts"]
    for value in contacts.values():
        assert value not in captured["system"]
        assert value not in captured["user"]
    assert result["contacts"] == contacts


def test_check_bullet_directly_for_each_category():
    sources = {"b1": "Shipped feature X serving 100 users at Acme Corp."}
    assert check_bullet("Shipped feature.", None, sources) == ["missing_citation"]
    assert check_bullet("Shipped feature.", "nope", sources) == ["invalid_citation_id"]
    assert check_bullet("Shipped feature X serving 500 users at Acme Corp.", "b1", sources) == ["unsupported_fact"]
    assert check_bullet("Shipped feature X serving 100 users at Initech.", "b1", sources) == ["unsupported_fact"]
    assert check_bullet("Shipped feature X serving 100 users at Acme Corp.", "b1", sources) == []


@pytest.mark.skipif(
    not (os.environ.get("GROQ_API_KEY") and os.environ.get("RUN_LIVE_GROQ") == "1"),
    reason="optional manual live Groq run; set GROQ_API_KEY and RUN_LIVE_GROQ=1 to run",
)
def test_live_groq_tailors_dummy_profile():
    dummy_profile = {
        "contacts": {"name": "Test User", "email": "test@example.com", "phone": "000"},
        "roles": [{"id": "r1", "company": "Dummy Co", "title": "Engineer"}],
        "bullets": [{"id": "b1", "role_id": "r1", "text": "Built a dummy feature used by 10 test users."}],
        "stories": [],
    }
    result = tailor("Hiring an engineer to build features.", dummy_profile)
    assert "bullets" in result
    assert result["contacts"] == dummy_profile["contacts"]


def test_every_uncited_saved_bullet_is_added_as_fallback():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Led a team of 5 engineers to ship the checkout redesign at Acme Corp.",
         "source_id": "bullet_1"},
    ])):
        result = tailor(JOB_TEXT, PROFILE)
    first, *fallback = result["bullets"]
    assert first["fallback"] is False
    saved = {b["id"]: b["text"] for b in PROFILE["bullets"]}
    want = [f"bullet_{i}" for i in (2, 3, 7, 9, 4, 5, 6, 8, 10)]
    assert [(b["source_id"], b["text"]) for b in fallback] == [(i, saved[i]) for i in want]
    assert all(b["fallback"] and b["flags"] == [] for b in fallback)


def test_partly_cited_role_keeps_rest_in_order_and_uncited_role_keeps_all():
    profile = {"roles": [{"id": "a", "company": "A", "title": "T"}, {"id": "b", "company": "B", "title": "T"}],
               "bullets": [{"id": f"a{i}", "role_id": "a", "text": f"Did A thing {i}."} for i in range(3)]
               + [{"id": f"b{i}", "role_id": "b", "text": f"Did B thing {i}."} for i in range(4)],
               "stories": []}
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Did A thing 1.", "source_id": "a1"}])):
        result = tailor(JOB_TEXT, profile)
    fallback = [b for b in result["bullets"] if b["fallback"]]
    assert [b["source_id"] for b in fallback] == ["a0", "a2", "b0", "b1", "b2", "b3"]
    assert all(b["flags"] == [] for b in fallback)


def test_prompt_groups_sources_by_role_and_asks_to_cover_every_role():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([])) as mock:
        tailor(JOB_TEXT, PROFILE)
    system, user = mock.call_args.args
    assert "every role" in system and "every saved bullet" in system
    roles = json.loads(user)["roles"]
    assert [r["id"] for r in roles] == ["role_1", "role_2"]
    assert "bullet_4" in roles[1]["sources"] and "bullet_4" not in roles[0]["sources"]
    assert "story_1" in roles[0]["sources"]


def test_non_string_source_id_is_flagged_not_a_crash():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Shipped it.", "source_id": ["bullet_1"]}])):
        result = tailor(JOB_TEXT, PROFILE)
    assert result["bullets"][0]["flags"]
    assert "bullet_1" in [b["source_id"] for b in result["bullets"] if b["fallback"]]
