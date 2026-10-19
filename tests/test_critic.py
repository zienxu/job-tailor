import copy
import json
from pathlib import Path
from unittest.mock import patch

from src.api.critic import KEYS, critique

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE = json.loads((FIXTURES / "profile.json").read_text())
JOB_TEXT = (FIXTURES / "job.txt").read_text()
RESUME = {
    "contacts": PROFILE["contacts"],
    "bullets": [{"text": b["text"], "source_id": b["id"], "flags": []} for b in PROFILE["bullets"]],
}
MOCK = json.dumps({
    "unmet_must_haves": ["CI/CD pipelines"],
    "weak_bullets": [{"text": "Onboarded 4 new hires onto the platform team.", "reason": "no outcome"}],
    "missing_keywords": ["reliability"],
    "overstated_claims": [{"text": "Designed REST APIs used by 3 million users.", "reason": "scale unclear"}],
})


def test_mocked_critic_output_parses():
    with patch("src.api.critic.llm.complete", return_value=MOCK):
        result = critique(JOB_TEXT, RESUME)
    assert result == json.loads(MOCK)


def test_resume_identical_before_and_after():
    before = copy.deepcopy(RESUME)
    with patch("src.api.critic.llm.complete", return_value=MOCK):
        critique(JOB_TEXT, RESUME)
    assert RESUME == before


def test_contacts_never_reach_the_llm_call():
    captured = {}

    def fake(system_prompt, user_prompt):
        captured["prompt"] = system_prompt + user_prompt
        return MOCK

    with patch("src.api.critic.llm.complete", side_effect=fake):
        critique(JOB_TEXT, RESUME)
    for value in RESUME["contacts"].values():
        assert value not in captured["prompt"]


def test_unparseable_or_wrong_shape_fails_closed():
    wrong_items = {**json.loads(MOCK), "weak_bullets": ["just a string"]}
    for bad in ["not json", json.dumps({"weak_bullets": "oops"}), json.dumps(wrong_items), "[]"]:
        with patch("src.api.critic.llm.complete", return_value=bad):
            result = critique(JOB_TEXT, RESUME)
        assert result["error"] == "unparseable_response"
        assert all(result[k] == [] for k in KEYS)


def test_llm_call_failure_is_reported_as_such():
    with patch("src.api.critic.llm.complete", side_effect=KeyError("GROQ_API_KEY")):
        result = critique(JOB_TEXT, RESUME)
    assert result["error"] == "llm_call_failed"
    assert all(result[k] == [] for k in KEYS)
