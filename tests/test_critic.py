import copy
import json
from pathlib import Path
from unittest.mock import patch

from src.api.critic import critique

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE = json.loads((FIXTURES / "profile.json").read_text())
JOB_TEXT = (FIXTURES / "job.txt").read_text()
RESUME = {
    "contacts": PROFILE["contacts"],
    "bullets": [{"text": b["text"], "source_id": b["id"], "flags": []} for b in PROFILE["bullets"]],
}
SOURCES = {b["id"]: b["text"] for b in PROFILE["bullets"]}
READINESS = {"verdict": "needs_work", "reason": "no CI/CD evidence"}


def items(n):
    return [{"bullet": f"b{i}", "problem": f"p{i}", "fix": f"f{i}"} for i in range(n)]


MOCK = json.dumps({"items": items(3), "readiness": READINESS})


def run(raw, sources=SOURCES):
    with patch("src.api.critic.llm.complete", return_value=raw):
        return critique(JOB_TEXT, RESUME, sources)


def test_mocked_critic_output_parses():
    assert run(MOCK) == json.loads(MOCK)


def test_seven_items_cut_to_first_five_and_four_kept_whole():
    assert run(json.dumps({"items": items(7), "readiness": READINESS}))["items"] == items(5)
    assert run(json.dumps({"items": items(4), "readiness": READINESS}))["items"] == items(4)

    bad_sixth = items(5) + [{"bullet": "b5"}]
    assert run(json.dumps({"items": bad_sixth, "readiness": READINESS})) == {"items": items(5), "readiness": READINESS}


def test_old_keys_absent():
    old = {"unmet_must_haves": ["x"], "missing_keywords": ["y"], "weak_bullets": [], "overstated_claims": []}
    result = run(json.dumps({"items": items(3), "readiness": READINESS, **old}))
    assert set(result) == {"items", "readiness"}


def test_cited_source_text_in_prompt():
    captured = {}

    def fake(system_prompt, user_prompt):
        captured["prompt"] = user_prompt
        return MOCK

    resume = {"bullets": [{"text": "Rewritten claim.", "source_id": "src_1"}]}
    with patch("src.api.critic.llm.complete", side_effect=fake):
        critique(JOB_TEXT, resume, {"src_1": "Original saved record of the claim."})
    assert "Original saved record of the claim." in captured["prompt"]


def test_resume_identical_before_and_after():
    before = copy.deepcopy(RESUME)
    run(MOCK)
    assert RESUME == before


def test_contacts_never_reach_the_llm_call():
    captured = {}

    def fake(system_prompt, user_prompt):
        captured["prompt"] = system_prompt + user_prompt
        return MOCK

    with patch("src.api.critic.llm.complete", side_effect=fake):
        critique(JOB_TEXT, RESUME, SOURCES)
    for value in RESUME["contacts"].values():
        assert value not in captured["prompt"]


def test_unparseable_or_wrong_shape_fails_closed():
    bads = ["not json", json.dumps({"items": "oops", "readiness": READINESS}),
            json.dumps({"items": ["just a string"], "readiness": READINESS}),
            json.dumps({"items": [{"bullet": "b", "problem": "p"}], "readiness": READINESS}), "[]"]
    for bad in bads:
        result = run(bad)
        assert result["error"] == "unparseable_response"
        assert result["items"] == []


def test_bad_readiness_fails_closed():
    good = json.loads(MOCK)
    bads = [{**good, "readiness": {"verdict": "maybe", "reason": "x"}},
            {**good, "readiness": {"verdict": "ready"}},
            {"items": good["items"]}]
    for bad in bads:
        result = run(json.dumps(bad))
        assert result["error"] == "unparseable_response"
        assert result["readiness"] is None


def test_llm_call_failure_is_reported_as_such():
    with patch("src.api.critic.llm.complete", side_effect=KeyError("GROQ_API_KEY")):
        result = critique(JOB_TEXT, RESUME, SOURCES)
    assert result["error"] == "llm_call_failed"
    assert result["items"] == []
