import json
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import db
from src.api.fit import band, grade
from src.api.main import app

FIXTURES = Path(__file__).parent / "fixtures"
PROFILE = json.loads((FIXTURES / "profile.json").read_text())
JOB_TEXT = (FIXTURES / "job.txt").read_text()
B1, B2 = PROFILE["bullets"][0]["id"], PROFILE["bullets"][1]["id"]


def _req(kind, status, ids, gate=False):
    return {"text": f"{kind} {status}", "kind": kind, "hard_gate": gate, "status": status, "evidence_ids": ids}


def _mock(reqs, keywords=None):
    return json.dumps({"requirements": reqs, "keywords": keywords or [{"term": "Python", "kind": "must"}]})


def _grade(reqs):
    with patch("src.api.fit.llm.complete", return_value=_mock(reqs)):
        return grade(JOB_TEXT, PROFILE)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    return TestClient(app)


def test_formula_mixed_fixture():
    # must met 2 + must partial 1 + must missing 0 + nice met 1 + nice partial 0.5 = 4.5 of 8
    result = _grade([_req("must", "met", [B1]), _req("must", "partial", [B2]), _req("must", "missing", []),
                     _req("nice", "met", [B1]), _req("nice", "partial", [B2])])
    assert result["score"] == 3.3  # 1 + 4 * 4.5/8 = 3.25, rounded half-up
    assert result["band"] == "Stretch"
    assert result["keywords"] == [{"term": "Python", "kind": "must"}]


def test_score_rounds_half_up():
    # 4 met (8) + 1 partial (1) + 3 missing musts = 9/16 -> 1 + 4 * 0.5625 = 3.25
    result = _grade([_req("must", "met", [B1])] * 4 + [_req("must", "partial", [B1])] + [_req("must", "missing", [])] * 3)
    assert result["score"] == 3.3


def test_band_boundaries():
    assert [band(s) for s in (3.8, 3.7, 3.0, 2.9)] == ["Apply", "Stretch", "Stretch", "Skip"]


def test_missing_hard_gate_caps_at_stretch():
    # 7 met musts (14) + 1 missing hard-gate must (0) -> coverage 14/16, score 4.5
    result = _grade([_req("must", "met", [B1])] * 7 + [_req("must", "missing", [], gate=True)])
    assert (result["score"], result["band"]) == (4.5, "Stretch")


def test_unknown_evidence_id_counts_as_missing():
    result = _grade([_req("must", "met", ["bullet_999"]), _req("must", "met", [B1])])
    assert [r["status"] for r in result["requirements"]] == ["missing", "met"]
    assert result["requirements"][0]["evidence_ids"] == []
    assert result["score"] == 3.0


def test_contacts_never_reach_the_llm_call():
    captured = {}

    def fake(system_prompt, user_prompt):
        captured["prompt"] = system_prompt + user_prompt
        return _mock([_req("must", "met", [B1])])

    with patch("src.api.fit.llm.complete", side_effect=fake):
        grade(JOB_TEXT, PROFILE)
    for value in PROFILE["contacts"].values():
        assert value not in captured["prompt"]


@pytest.mark.parametrize("raw", ["not json", json.dumps({"requirements": []}), json.dumps([1]),
                                 _mock([_req("must", "sorta", [])]), _mock([_req("must", "met", "bullet_1")]),
                                 _mock([_req("must", "met", [])], keywords=[{"term": "x", "kind": "maybe"}])])
def test_bad_response_fails_closed_and_stores_nothing(client, raw):
    job_id = client.post("/jobs", json={"text": "Need Python"}).json()["id"]
    with patch("src.api.fit.llm.complete", return_value=raw):
        r = client.post(f"/jobs/{job_id}/grade")
    assert r.status_code == 502 and "Need Python" not in r.text
    assert client.get(f"/jobs/{job_id}").json()["grade"] is None


def test_grade_stored_and_education_and_skills_reach_prompt(client):
    edu = client.post("/roles", json={"company": "NUS", "title": "BComp", "kind": "education"}).json()["id"]
    bid = client.post("/bullets", json={"role_id": edu, "text": "Dean's list"}).json()["id"]
    sid = client.post("/entries", json={"section": "skills", "label": "Languages", "text": "Python, Go"}).json()["id"]
    job_id = client.post("/jobs", json={"text": "Need a degree"}).json()["id"]
    captured = {}

    def fake(system_prompt, user_prompt):
        captured["prompt"] = user_prompt
        return _mock([_req("must", "met", [f"role_{edu}"], gate=True), _req("nice", "met", [f"skill_{sid}"])])

    with patch("src.api.fit.llm.complete", side_effect=fake):
        r = client.post(f"/jobs/{job_id}/grade")
    assert r.status_code == 200, r.text
    for text in ("NUS", "BComp", "Dean's list", f"bullet_{bid}", "Python, Go", f"skill_{sid}"):
        assert text in captured["prompt"]
    assert (r.json()["score"], r.json()["band"]) == (5.0, "Apply")
    assert [q["evidence"] for q in r.json()["requirements"]] == [["NUS, BComp"], ["Languages: Python, Go"]]
    assert client.get(f"/jobs/{job_id}").json()["grade"] == r.json()
    client.post(f"/jobs/{job_id}/versions", json={"content": {"bullets": []}})
    assert client.get("/jobs").json()[0]["grade"] == r.json()
    assert client.put(f"/jobs/{job_id}", json={"notes": "x"}).json()["grade"] == r.json()
    assert client.post("/jobs", json={"text": "New"}).json()["grade"] is None


def test_old_db_without_grade_migrates(client):
    with closing(sqlite3.connect(db.DB_PATH)) as old:
        old.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL)")
        old.execute("INSERT INTO jobs (text) VALUES ('Old job')")
        old.commit()
    job = client.get("/jobs/1").json()
    assert (job["text"], job["grade"]) == ("Old job", None)


def test_eligibility_facts_reach_only_the_grade(client):
    fid = client.post("/entries", json={"section": "eligibility", "label": "Work eligibility",
                                        "text": "Singapore Citizen; available from 2027"}).json()["id"]
    job_id = client.post("/jobs", json={"text": "Singapore Citizen or PR only"}).json()["id"]
    captured = {}

    def fake(system_prompt, user_prompt):
        captured["prompt"] = user_prompt
        return _mock([_req("must", "met", [f"fact_{fid}"], gate=True)])

    with patch("src.api.fit.llm.complete", side_effect=fake):
        r = client.post(f"/jobs/{job_id}/grade").json()
    assert "Singapore Citizen; available from 2027" in captured["prompt"]
    assert r["requirements"][0]["status"] == "met" and r["band"] == "Apply"
    assert r["requirements"][0]["evidence"] == ["Work eligibility: Singapore Citizen; available from 2027"]
    with closing(db.connect()) as conn:
        assert "facts" not in db.load_profile(conn)  # the tailor's profile
