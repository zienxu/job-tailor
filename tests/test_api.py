import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import db
from src.api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.mark.parametrize("table", ["bullets", "stories"])
def test_crud_round_trip(client, table):
    role = client.post("/roles", json={"company": "Acme Corp", "title": "Software Engineer",
                                       "start_date": "2020", "end_date": "2023"})
    assert role.status_code == 201
    role_id = role.json()["id"]
    assert client.get(f"/roles/{role_id}").json()["company"] == "Acme Corp"
    assert client.put(f"/roles/{role_id}", json={"company": "Acme", "title": "SWE"}).json()["title"] == "SWE"

    item = client.post(f"/{table}", json={"role_id": role_id, "text": "Shipped a thing."}).json()
    assert client.get(f"/{table}/{item['id']}").json()["text"] == "Shipped a thing."
    client.put(f"/{table}/{item['id']}", json={"role_id": role_id, "text": "Shipped two things."})
    assert [i["text"] for i in client.get(f"/{table}").json()] == ["Shipped two things."]

    assert client.delete(f"/{table}/{item['id']}").status_code == 204
    assert client.get(f"/{table}/{item['id']}").status_code == 404


def test_unknown_role_rejected(client):
    assert client.post("/bullets", json={"role_id": 999, "text": "x"}).status_code == 422


def test_deleting_role_cascades(client):
    role_id = client.post("/roles", json={"company": "Acme", "title": "SWE"}).json()["id"]
    client.post("/bullets", json={"role_id": role_id, "text": "x"})
    client.delete(f"/roles/{role_id}")
    assert client.get("/bullets").json() == []


def test_deleted_id_is_never_reused(client):
    role_id = client.post("/roles", json={"company": "Acme", "title": "SWE"}).json()["id"]
    old = client.post("/bullets", json={"role_id": role_id, "text": "x"}).json()["id"]
    client.delete(f"/bullets/{old}")
    assert client.post("/bullets", json={"role_id": role_id, "text": "y"}).json()["id"] != old


def test_tailor_returns_flagged_draft(client):
    role_id = client.post("/roles", json={"company": "Acme Corp", "title": "Software Engineer"}).json()["id"]
    b = client.post("/bullets", json={"role_id": role_id,
                                      "text": "Reduced page load time by 40% through caching."}).json()
    job_id = client.post("/jobs", json={"text": "Need caching and performance skills."}).json()["id"]

    llm_out = json.dumps({"bullets": [
        {"text": "Reduced page load time by 40% with caching.", "source_id": f"bullet_{b['id']}"},
        {"text": "Reduced page load time by 90% with caching.", "source_id": f"bullet_{b['id']}"},
    ]})
    with patch("src.api.tailor.llm.complete", return_value=llm_out) as mock:
        resp = client.post(f"/jobs/{job_id}/tailor")
    assert resp.status_code == 200
    assert [x["flags"] for x in resp.json()["bullets"]] == [[], ["unsupported_fact"]]
    assert f"bullet_{b['id']}" in mock.call_args.args[1]


def test_tailor_llm_failure_is_502(client):
    job_id = client.post("/jobs", json={"text": "job"}).json()["id"]
    with patch("src.api.tailor.llm.complete", side_effect=KeyError("GROQ_API_KEY")):
        resp = client.post(f"/jobs/{job_id}/tailor")
    assert resp.status_code == 502


def test_blank_text_rejected(client):
    role_id = client.post("/roles", json={"company": "Acme", "title": "SWE"}).json()["id"]
    assert client.post("/jobs", json={"text": "  "}).status_code == 422
    assert client.post("/bullets", json={"role_id": role_id, "text": ""}).status_code == 422


def test_tailor_unknown_job_404(client):
    assert client.post("/jobs/999/tailor").status_code == 404


def test_two_saves_make_two_versions(client):
    job_id = client.post("/jobs", json={"text": "job", "company": "Globex"}).json()["id"]
    v1 = client.post(f"/jobs/{job_id}/versions", json={"content": {"bullets": ["a"]}}).json()
    v2 = client.post(f"/jobs/{job_id}/versions", json={"content": {"bullets": ["b"]}}).json()
    assert v1["id"] != v2["id"]
    versions = client.get(f"/jobs/{job_id}/versions").json()
    assert [v["content"] for v in versions] == [{"bullets": ["a"]}, {"bullets": ["b"]}]
