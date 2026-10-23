import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.api.tailor import SYSTEM_PROMPT, tailor
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


STORY = ("At Acme Corp I noticed builds were slow. I profiled the pipeline, found redundant steps, "
         "and added caching across 12 services, which cut build time by 40% and made releases calmer for everyone.")


def test_story_bullet_must_be_one_short_sentence():
    sources = {"story_1": STORY, "bullet_1": STORY}
    one = "Cut build time by 40% by adding caching across 12 services at Acme Corp."
    assert check_bullet(one, "story_1", sources) == []
    assert check_bullet("Profiled the pipeline. Added caching across 12 services.", "story_1", sources) == ["story_too_long"]
    assert check_bullet("e.g. caching across 12 services cut build time by 40%.", "story_1", sources) == []
    assert check_bullet(" ".join(["caching"] * 31), "story_1", sources) == ["story_too_long"]
    assert check_bullet(STORY, "bullet_1", sources) == []  # saved bullets are never length-checked
    assert check_bullet(STORY.replace("12", "99"), "story_1", sources) == ["unsupported_fact"]  # a fact flag wins


def test_prompt_asks_for_one_sentence_story_bullets():
    assert "one resume-style sentence of at most 30 words" in SYSTEM_PROMPT


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
    assert "every role" in system and "at most 3" in system
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


def _role_profile(n_saved):
    return {"roles": [{"id": "a", "company": "A", "title": "T"}],
            "bullets": [{"id": f"a{i}", "role_id": "a", "text": f"Did A thing {i} for 5 users."} for i in range(n_saved)],
            "stories": []}


def test_best_3_per_role_unflagged_first_then_job_term_hits():
    job = "Need python, kubernetes and caching."
    reply = mock_response([
        {"text": "Did A thing 0 for 5 users.", "source_id": "a0"},                                  # 0 hits
        {"text": "Did A thing 1 for 5 users with python.", "source_id": "a1"},                      # 1 hit
        {"text": "Did A thing 2 for 99 users with python, kubernetes, caching.", "source_id": "a2"},  # flagged
        {"text": "Did A thing 3 for 5 users with python and kubernetes.", "source_id": "a3"},       # 2 hits
        {"text": "Did A thing 4 for 5 users with caching.", "source_id": "a4"},                     # 1 hit, after a1
    ])
    with patch("src.api.tailor.llm.complete", return_value=reply):
        out = tailor(job, _role_profile(5))["bullets"]
    assert out[2]["flags"] == ["unsupported_fact"]
    assert [b["source_id"] for b in out if b["included"]] == ["a1", "a3", "a4"]
    assert sum(b["included"] for b in out) == 3


def test_role_with_one_llm_bullet_is_not_padded():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([
        {"text": "Did A thing 2 for 5 users.", "source_id": "a2"}])):
        out = tailor(JOB_TEXT, _role_profile(4))["bullets"]
    assert [(b["source_id"], b["included"]) for b in out] == [
        ("a2", True), ("a0", False), ("a1", False), ("a3", False)]
    assert all(b["fallback"] for b in out[1:])


def test_uncited_role_includes_only_its_first_saved_bullet():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([])):
        out = tailor(JOB_TEXT, _role_profile(3))["bullets"]
    assert [(b["source_id"], b["included"], b["fallback"]) for b in out] == [
        ("a0", True, True), ("a1", False, True), ("a2", False, True)]


def test_uncited_llm_bullet_stays_included_and_flagged():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([{"text": "Made it up."}])):
        out = tailor(JOB_TEXT, _role_profile(1))["bullets"]
    assert out[0]["included"] and out[0]["flags"] == ["missing_citation"]


def test_bold_markers_do_not_change_fact_check_or_ats_score():
    from src.api.ats import score
    assert check_bullet("Cut costs by **40%** at **Acme**", "s", {"s": "Cut costs by 40% at Acme"}) == []
    assert check_bullet("Cut costs by 41%", "s", {"s": "Cut **costs** by **40%**"}) == ["unsupported_fact"]
    assert score("python sql", "**Python** and SQL") == score("python sql", "Python and SQL")


def test_prompt_asks_to_keep_bold_markers():
    with patch("src.api.tailor.llm.complete", return_value=mock_response([])) as mock:
        tailor(JOB_TEXT, PROFILE)
    assert "**" in mock.call_args.args[0]


def _pool(n=16, flags={}):
    return [{"id": f"skill_{i}", "name": f"S{i}", "aliases": "", "is_default": i <= 13, "demote": False,
             **flags.get(i, {})} for i in range(1, n + 1)]


def test_pick_skills_drops_unknown_and_dupes_caps_and_pads_from_defaults():
    from src.api.tailor import pick_skills
    pool = _pool()
    assert pick_skills(["skill_16", "nope", "skill_16", "skill_15"], pool, [])[:2] == ["skill_16", "skill_15"]
    assert len(pick_skills(["skill_16", "nope", "skill_16"], pool, [])) == 12  # padded from defaults to 12
    assert len(pick_skills([f"skill_{i}" for i in range(1, 17)], pool, [])) == 14  # capped
    assert pick_skills("junk", pool, []) == [f"skill_{i}" for i in range(1, 14)]  # bad shape = every default
    assert pick_skills([], _pool(20, {i: {"is_default": True} for i in range(1, 21)}), []) == [
        f"skill_{i}" for i in range(1, 15)]  # every default, capped


def test_demoted_skill_leaves_the_first_five_unless_a_must_have_names_it():
    from src.api.tailor import pick_skills
    pool = _pool(16, {2: {"name": "SQL", "aliases": "Postgres, MySQL", "demote": True}})
    ids = [f"skill_{i}" for i in range(1, 13)]
    assert pick_skills(ids, pool, []).index("skill_2") == 5  # ungraded job: stays down
    assert pick_skills(ids, pool, ["Python"]).index("skill_2") == 5
    assert pick_skills(ids, pool, ["SQL"]).index("skill_2") == 1  # a must keyword
    assert pick_skills(ids, pool, ["Strong SQL skills for reporting"]).index("skill_2") == 1  # a must requirement
    assert pick_skills(ids, pool, ["Experience with MySQL"]).index("skill_2") == 1  # a listed alias


def test_prompt_carries_pool_ids_names_and_aliases_only():
    profile = {**PROFILE, "skill_pool": _pool(2, {1: {"aliases": "Postgres"}})}
    with patch("src.api.tailor.llm.complete", return_value=mock_response([])) as mock:
        tailor(JOB_TEXT, profile)
    pool = json.loads(mock.call_args.args[1])["skill_pool"]
    assert pool == [{"id": "skill_1", "name": "S1", "aliases": "Postgres"}, {"id": "skill_2", "name": "S2", "aliases": ""}]


def test_tailor_returns_picked_skills_and_defaults_on_a_bad_response():
    profile = {**PROFILE, "skill_pool": _pool()}
    with patch("src.api.tailor.llm.complete", return_value=json.dumps({"bullets": [], "skills": ["skill_16"]})):
        assert tailor(JOB_TEXT, profile)["skills"][0] == "skill_16"
    with patch("src.api.tailor.llm.complete", return_value="not json"):
        assert tailor(JOB_TEXT, profile)["skills"][0] == "skill_1"


def test_prompt_asks_for_british_spelling_and_no_semicolons_hyphens_or_final_full_stop():
    assert "British spelling" in SYSTEM_PROMPT
    assert "Never use semicolons, colons or hyphens" in SYSTEM_PROMPT
    assert "do not end a bullet with a full stop" in SYSTEM_PROMPT
