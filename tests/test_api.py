import json
import sqlite3
from contextlib import closing
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


def test_role_kind_round_trip(client):
    assert client.post("/roles", json={"company": "Acme", "title": "SWE"}).json()["kind"] == "experience"
    role = client.post("/roles", json={"company": "Chess AI", "title": "Course Project, NUS", "kind": "project"}).json()
    assert client.get(f"/roles/{role['id']}").json()["kind"] == "project"
    put = client.put(f"/roles/{role['id']}", json={"company": "NUS", "title": "BComp", "kind": "education"})
    assert put.json()["kind"] == "education"
    put = client.put(f"/roles/{role['id']}", json={"company": "NUS", "title": "BSc"})
    assert put.json()["kind"] == "education"  # omitted field is kept, not reset to the default
    assert client.post("/roles", json={"company": "x", "title": "y", "kind": "hobby"}).status_code == 422


def test_entries_crud_round_trip(client):
    e = client.post("/entries", json={"section": "eligibility", "label": "Citizenship", "text": "SG"})
    assert e.status_code == 201
    eid = e.json()["id"]
    client.post("/entries", json={"section": "eligibility", "label": "Start", "text": "Now"})
    client.put(f"/entries/{eid}", json={"section": "eligibility", "label": "Citizenship", "text": "SG, PR"})
    assert [(x["label"], x["text"]) for x in client.get("/entries").json()] == [
        ("Citizenship", "SG, PR"), ("Start", "Now")]
    # Leadership lives in roles since step 7c2b and skills in skill_pool since 8j.
    for section in ("leadership", "skills", "hobbies"):
        assert client.post("/entries", json={"section": section, "label": "P", "text": "x"}).status_code == 422
    assert client.post("/entries", json={"section": "eligibility", "label": " ", "text": "b"}).status_code == 422
    # A grade-only eligibility fact can't be moved into another section.
    assert client.put(f"/entries/{eid}", json={"section": "skills", "label": "C", "text": "SG"}).status_code == 422
    assert client.delete(f"/entries/{eid}").status_code == 204
    assert client.get(f"/entries/{eid}").status_code == 404


def test_summary_templates_crud_and_kept_out_of_profiles(client):
    t = client.post("/entries", json={"section": "summary", "label": "PM / APM", "text": "PM role in [domain]."})
    assert t.status_code == 201
    client.put(f"/entries/{t.json()['id']}", json={"section": "summary", "label": "PM / APM", "text": "PM in [domain]."})
    assert [(x["section"], x["text"]) for x in client.get("/entries").json()] == [("summary", "PM in [domain].")]
    assert client.put(f"/entries/{t.json()['id']}", json={"section": "eligibility", "label": "x", "text": "y"}).status_code == 422
    with closing(db.connect()) as conn:
        for full in (False, True):
            assert "PM in" not in json.dumps(db.load_profile(conn, full=full))


@pytest.mark.parametrize("reply,ok", [
    ('{"kind": "pm", "domain": " digital payments ", "company": "Acme", "programme": "payments app"}', True),
    ('{"kind": "pm", "domain": "digital payments", "company": "", "programme": ""}', True),  # none in the posting
    ('{"kind": "designer", "domain": "payments", "company": "", "programme": ""}', False),
    ('{"kind": "pm", "domain": "one two three four five six seven", "company": "", "programme": ""}', False),
    ('{"kind": "pm", "company": "", "programme": ""}', False),
    ('{"kind": "pm", "domain": "digital payments"}', False),  # company and programme keys are required
    ('{"kind": "pm", "domain": "healthcare", "company": "", "programme": ""}', False),  # not in the posting
    ('{"kind": "pm", "domain": "payments", "company": "Globex", "programme": ""}', False),  # company not in posting
    ('{"kind": "pm", "domain": "payments", "company": 5, "programme": ""}', False),
    ('{"kind": "pm", "domain": "payments", "company": "s", "programme": ""}', False),  # stray letter, not a word
    ('{"kind": "pm", "domain": "payments", "company": "", "programme": "."}', False),
    ("not json", False),
])
def test_summary_hint(client, reply, ok):
    role = client.post("/roles", json={"company": "SecretCo", "title": "SWE"}).json()["id"]
    client.post("/bullets", json={"role_id": role, "text": "Private bullet"})
    text = "Acme PM for a digital payments app"
    job = client.post("/jobs", json={"text": text}).json()["id"]
    with patch("src.api.main.llm.complete", return_value=reply) as mock:
        r = client.post(f"/jobs/{job}/summary-hint")
    assert mock.call_args.args[1] == text  # job text only, no profile
    if ok:
        assert r.status_code == 200 and r.json()["domain"] == "digital payments"
        assert r.json()["company"] in ("Acme", "") and set(r.json()) == {"kind", "domain", "company", "programme"}
    else:
        assert r.status_code == 502


def test_education_excluded_from_profile(client):
    work = client.post("/roles", json={"company": "Acme", "title": "SWE"}).json()["id"]
    proj = client.post("/roles", json={"company": "Chess AI", "title": "Project", "kind": "project"}).json()["id"]
    edu = client.post("/roles", json={"company": "NUS", "title": "BComp", "kind": "education"}).json()["id"]
    for rid in (work, proj, edu):
        client.post("/bullets", json={"role_id": rid, "text": f"bullet {rid}"})
        client.post("/stories", json={"role_id": rid, "text": f"story {rid}"})
    with closing(db.connect()) as conn:
        profile = db.load_profile(conn)
    assert [r["id"] for r in profile["roles"]] == [f"role_{work}", f"role_{proj}"]
    for table in ("bullets", "stories"):
        assert {x["role_id"] for x in profile[table]} == {f"role_{work}", f"role_{proj}"}


def test_old_db_without_kind_migrates(client):
    old = sqlite3.connect(db.DB_PATH)
    old.execute("CREATE TABLE roles (id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL,"
                " title TEXT NOT NULL, start_date TEXT NOT NULL DEFAULT '', end_date TEXT NOT NULL DEFAULT '')")
    old.execute("INSERT INTO roles (company, title) VALUES ('Acme', 'SWE')")
    old.commit()
    old.close()
    assert [r["kind"] for r in client.get("/roles").json()] == ["experience"]


@pytest.mark.parametrize("table,body", [
    ("roles", lambda i: {"company": f"C{i}", "title": "T"}),
    ("skill_pool", lambda i: {"name": f"S{i}", "grp": ["Technical", "AI", "Product"][i]}),  # groups never block a swap
])
def test_swap_changes_order(client, table, body):
    ids = [client.post(f"/{table}", json=body(i)).json()["id"] for i in range(3)]
    assert [r["position"] for r in client.get(f"/{table}").json()] == ids  # initial position = id
    assert client.post(f"/{table}/{ids[0]}/swap/{ids[2]}").status_code == 204
    assert [r["id"] for r in client.get(f"/{table}").json()] == [ids[2], ids[1], ids[0]]
    assert client.post(f"/{table}/{ids[0]}/swap/999").status_code == 404


@pytest.mark.parametrize("table,x,y", [
    ("roles", {"company": "Acme", "title": "SWE"}, {"company": "NUS", "title": "BComp", "kind": "education"}),
])
def test_swap_across_groups_rejected(client, table, x, y):
    a, b = (client.post(f"/{table}", json=body).json() for body in (x, y))
    assert client.post(f"/{table}/{a['id']}/swap/{b['id']}").status_code == 422
    assert [r["position"] for r in client.get(f"/{table}").json()] == [a["position"], b["position"]]


def test_bullet_reorder_keeps_ids(client):
    role_id = client.post("/roles", json={"company": "Acme", "title": "SWE"}).json()["id"]
    a = client.post("/bullets", json={"role_id": role_id, "text": "A"}).json()["id"]
    b = client.post("/bullets", json={"role_id": role_id, "text": "B"}).json()["id"]
    client.put(f"/bullets/{b}", json={"role_id": role_id, "text": "B", "position": 0})
    client.put(f"/bullets/{a}", json={"role_id": role_id, "text": "A", "position": 1})
    assert [(x["id"], x["text"]) for x in client.get("/bullets").json()] == [(b, "B"), (a, "A")]
    assert client.put(f"/bullets/{a}", json={"role_id": role_id, "text": "A", "position": None}).status_code == 422
    with closing(db.connect()) as conn:
        assert [x["id"] for x in db.load_profile(conn)["bullets"]] == [f"bullet_{b}", f"bullet_{a}"]


def test_old_db_without_position_migrates(client):
    old = sqlite3.connect(db.DB_PATH)
    old.executescript("""
        CREATE TABLE roles (id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL, title TEXT NOT NULL,
            start_date TEXT NOT NULL DEFAULT '', end_date TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'experience');
        CREATE TABLE bullets (id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE, text TEXT NOT NULL);
        CREATE TABLE entries (id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT NOT NULL,
            label TEXT NOT NULL, text TEXT NOT NULL);
        INSERT INTO roles (company, title) VALUES ('Acme', 'SWE'), ('Beta', 'SWE');
        INSERT INTO bullets (role_id, text) VALUES (1, 'A');
        INSERT INTO entries (section, label, text) VALUES ('skills', 'L', 'x');
    """)
    old.close()
    for table in ("roles", "bullets", "entries"):
        assert all(r["position"] == r["id"] for r in client.get(f"/{table}").json())
    new = client.post("/roles", json={"company": "Gamma", "title": "SWE"}).json()
    assert new["position"] == new["id"] == 3


def test_old_leadership_entries_migrate_to_roles(client):
    with closing(db.connect()) as conn:  # an old DB: rows written before connect() learned to move them
        conn.execute("INSERT INTO roles (company, title, kind) VALUES ('Old Club', 'Chair', 'leadership')")
        conn.executemany("INSERT INTO entries (section, label, text, position) VALUES (?, ?, ?, ?)", [
            ("leadership", "Debate", "Won 3 cups", 20), ("eligibility", "Citizenship", "SG", 5),
            ("leadership", "Chess Club:", "Led 20 members", 10)])
        conn.commit()
    roles = [r for r in client.get("/roles").json() if r["kind"] == "leadership"]
    assert [(r["company"], r["title"]) for r in roles] == [("Old Club", "Chair"), ("Chess Club", ""), ("Debate", "")]
    by_role = {b["role_id"]: b["text"] for b in client.get("/bullets").json()}
    assert [by_role.get(r["id"]) for r in roles[1:]] == ["Led 20 members", "Won 3 cups"]
    assert [e["section"] for e in client.get("/entries").json()] == ["eligibility"]

    snapshot = [client.get(f"/{t}").json() for t in ("roles", "bullets", "entries")]
    with closing(db.connect()):  # second run is a no-op
        pass
    assert [client.get(f"/{t}").json() for t in ("roles", "bullets", "entries")] == snapshot


def test_load_profile_includes_leadership_excludes_education(client):
    ids = {k: client.post("/roles", json={"company": k, "title": "", "kind": k}).json()["id"]
           for k in ("leadership", "education")}
    for rid in ids.values():
        client.post("/bullets", json={"role_id": rid, "text": "x"})
    with closing(db.connect()) as conn:
        profile = db.load_profile(conn)
    assert [r["id"] for r in profile["roles"]] == [f"role_{ids['leadership']}"]
    assert [b["role_id"] for b in profile["bullets"]] == [f"role_{ids['leadership']}"]


def test_old_skills_entries_migrate_to_the_pool_once(client):
    with closing(db.connect()) as conn:
        conn.execute("INSERT INTO entries (section, label, text) VALUES ('skills', 'Technical:', 'Python, Analysis (t-tests, SHAP), SQL')")
        conn.execute("INSERT INTO entries (section, label, text) VALUES ('skills', 'ai', 'RAG')")
        conn.execute("INSERT INTO entries (section, label, text) VALUES ('skills', 'Languages:', 'Go')")
        conn.commit()
    pool = client.get("/skill_pool").json()
    assert [(s["name"], s["grp"], s["is_default"]) for s in pool] == [
        ("Python", "Technical", 1), ("Analysis (t-tests, SHAP)", "Technical", 1), ("SQL", "Technical", 1),
        ("RAG", "AI", 1), ("Go", "Technical", 1)]  # an unknown old label becomes Technical
    assert client.get("/entries").json() == []
    with closing(db.connect()):  # second run is a no-op
        pass
    assert client.get("/skill_pool").json() == pool
