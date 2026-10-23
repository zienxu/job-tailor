import json
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import db
from src.api.main import app
from src.api.tailor import tailor

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.fixture
def seeded(client):
    role_id = client.post("/roles", json={"company": "Acme Corp", "title": "Engineer"}).json()["id"]
    b = client.post("/bullets", json={"role_id": role_id, "text": "Cut build time by 40% with caching."}).json()
    job_id = client.post("/jobs", json={"text": "Need kubernetes and caching."}).json()["id"]
    return client, job_id, f"role_{role_id}", f"bullet_{b['id']}"


def test_tailor_adds_role_id(seeded):
    client, job_id, role, bullet = seeded
    llm_out = json.dumps({"bullets": [{"text": "Cut build time by 40%.", "source_id": bullet},
                                      {"text": "Uncited.", "source_id": None}]})
    with patch("src.api.tailor.llm.complete", return_value=llm_out):
        out = client.post(f"/jobs/{job_id}/tailor").json()
    assert [b["role_id"] for b in out["bullets"]] == [role, None]
    assert [b["included"] for b in out["bullets"]] == [True, True]


def test_check_scores_and_rechecks_flags(seeded):
    client, job_id, _, bullet = seeded
    bad = client.post(f"/jobs/{job_id}/check", json={
        "text": "caching", "bullets": [{"text": "Cut build time by 90%.", "source_id": bullet}]}).json()
    fixed = client.post(f"/jobs/{job_id}/check", json={
        "text": "caching kubernetes", "bullets": [{"text": "Cut build time by 40%.", "source_id": bullet}]}).json()
    assert bad["flags"] == [["unsupported_fact"]] and fixed["flags"] == [[]]
    assert fixed["ats"]["score"] > bad["ats"]["score"]
    assert fixed["ats"]["label"] == "local estimate"


def test_check_returns_per_role_hits(seeded):
    client, job_id, _, _ = seeded
    out = client.post(f"/jobs/{job_id}/check", json={
        "text": "", "bullets": [], "roles": {"role_1": "Ran Kubernetes and caching", "role_2": "Wrote docs"}}).json()
    assert out["role_hits"] == {"role_1": 2, "role_2": 0}


def test_critique_passes_through(seeded):
    client, job_id, _, bullet = seeded
    item = {"bullet": "Did caching.", "problem": "vague", "fix": "add the 40%"}
    out = json.dumps({"items": [item], "readiness": {"verdict": "needs_work", "reason": "no kubernetes"}})
    with patch("src.api.critic.llm.complete", return_value=out) as mock:
        resp = client.post(f"/jobs/{job_id}/critique", json={"bullets": [{"text": "Did caching.", "source_id": bullet}]})
    assert resp.json()["items"] == [item]
    assert "Cut build time by 40% with caching." in mock.call_args.args[1]
    assert resp.json()["readiness"] == {"verdict": "needs_work", "reason": "no kubernetes"}
    assert "Did caching." in mock.call_args.args[1]


def test_preview_has_name_and_summary(client):
    html = client.post("/preview", json={"resume": {"name": "Jane Doe", "summary": "Backend engineer."}}).json()["html"]
    assert "Jane Doe" in html and "Backend engineer." in html and "/api/templates/" in html
    assert client.get("/templates/resume.css").status_code == 200


def test_preview_escapes_markup(client):
    html = client.post("/preview", json={"resume": {"name": "<script>x</script>"}}).json()["html"]
    assert "<script>x" not in html


def test_preview_returns_page_count(client):
    job_id = client.post("/jobs", json={"text": "python"}).json()["id"]
    out = client.post("/preview", json={"resume": {"name": "Jane"}, "job_id": job_id, "fallback": []}).json()
    assert (out["pages"], out["shorten"], out["remove"]) == (1, [], [])
    assert client.post("/preview", json={"resume": {}, "job_id": 999}).status_code == 404


def test_bad_resume_is_422_without_echo(client):
    resp = client.post("/preview", json={"resume": {"name": "Jane Doe", "experience": "jane@example.com"}})
    assert resp.status_code == 422
    assert "jane@example.com" not in resp.text


def test_pdf_download(client):
    resp = client.post("/pdf", json={"resume": {"name": "Jane Doe", "experience": [
        {"company": "Acme", "title": "Engineer", "dates": "2020 - 2023", "bullets": ["Shipped X."]}]}})
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_latest_version(client):
    assert client.get("/versions/latest").json() is None
    job_id = client.post("/jobs", json={"text": "job"}).json()["id"]
    client.post(f"/jobs/{job_id}/versions", json={"content": {"name": "A"}})
    client.post(f"/jobs/{job_id}/versions", json={"content": {"name": "B"}})
    assert client.get("/versions/latest").json()["content"] == {"name": "B"}


def test_happy_path_fixture_has_at_most_one_flag():
    profile = json.loads((FIXTURES / "profile.json").read_text())
    raw = (FIXTURES / "happy_tailor.json").read_text()
    with patch("src.api.tailor.llm.complete", return_value=raw):
        out = tailor((FIXTURES / "job.txt").read_text(), profile)
    assert len(out["bullets"]) == 12
    assert sum(1 for b in out["bullets"] if b["flags"]) <= 1


def test_preview_renders_all_sections_in_order(client):
    resume = {"name": "Jane", "order": ["skills", "projects", "experience", "education", "leadership", "summary"],
              "summary": "Sum.", "skills": [{"label": "Languages", "text": "Python"}],
              "projects": [{"name": "Tailor", "role": "Course Project, NUS", "dates": "2024", "bullets": ["Built it."]}],
              "experience": [{"company": "Acme", "title": "Engineer", "bullets": ["Shipped X."]}],
              "education": [{"school": "NUS", "degree": "BComp", "date": "2025", "details": ["GPA 4.5"]}],
              "leadership": [{"name": "Chess Club", "role": "", "dates": "2023", "bullets": ["Led it."]}]}
    html = client.post("/preview", json={"resume": resume}).json()["html"]
    pos = [html.index(f"<h2>{h}</h2>") for h in ("Skills", "Projects", "Experience", "Education", "Leadership", "Summary")]
    assert pos == sorted(pos)
    assert "<b>Languages:</b> Python" in html and "<li><b>Chess Club:</b> Led it.</li>" in html
    # Leadership is one compact line per role: no subtitle, no dates.
    leadership = html.split("<h2>Leadership</h2>", 1)[1].split("<h2>", 1)[0]
    assert "<i>" not in leadership and "2023" not in leadership
    assert "<i>Course Project, NUS</i>" in html and "GPA 4.5" in html
    assert client.post("/preview", json={"resume": {"order": ["footer"]}}).status_code == 422


def test_tailor_never_sends_or_falls_back_to_education(seeded):
    client, job_id, _, _ = seeded
    edu = client.post("/roles", json={"company": "NUS", "title": "BComp", "kind": "education"}).json()["id"]
    client.post("/bullets", json={"role_id": edu, "text": "GPA 4.5 secret"})
    with patch("src.api.tailor.llm.complete", return_value=json.dumps({"bullets": []})) as mock:
        out = client.post(f"/jobs/{job_id}/tailor").json()
    assert "GPA 4.5" not in mock.call_args.args[1]
    assert [b["text"] for b in out["bullets"]] == ["Cut build time by 40% with caching."]
    assert out["bullets"][0]["fallback"] is True and out["bullets"][0]["flags"] == []


def test_zero_bullet_role_renders_header_only(client):
    html = client.post("/preview", json={"resume": {"experience": [
        {"company": "Acme Corp", "title": "Engineer", "dates": "2020", "bullets": []}]}}).json()["html"]
    assert "Engineer" in html and "<li>" not in html.split("Acme Corp", 1)[1]


def test_uncited_leadership_role_gets_fallback_bullets(seeded):
    client, job_id, _, bullet_id = seeded
    lead = client.post("/roles", json={"company": "Chess Club", "title": "", "kind": "leadership"}).json()["id"]
    for t in ("Led 20 members.", "Ran weekly sessions.", "Booked venues."):
        client.post("/bullets", json={"role_id": lead, "text": t})
    reply = json.dumps({"bullets": [{"text": "Cut build time by 40% with caching.", "source_id": bullet_id}]})
    with patch("src.api.tailor.llm.complete", return_value=reply) as mock:
        out = client.post(f"/jobs/{job_id}/tailor").json()
    assert "Chess Club" in mock.call_args.args[1]
    fallback = [b for b in out["bullets"] if b["fallback"]]
    assert [b["text"] for b in fallback] == ["Led 20 members.", "Ran weekly sessions.", "Booked venues."]
    assert all(b["flags"] == [] and b["role_id"] == f"role_{lead}" for b in fallback)


def test_leadership_renders_one_line_per_role(client):
    html = client.post("/preview", json={"resume": {"leadership": [
        {"name": "Chess Club", "role": "President", "dates": "2023", "bullets": ["a", "b"]},
        {"name": "Debate", "role": "Captain", "dates": "", "bullets": []},
        {"name": "Drama", "role": "", "dates": "", "bullets": []}]}}).json()["html"]
    assert "<li><b>Chess Club (President):</b> a b</li>" in html
    assert "<li><b>Debate (Captain)</b></li>" in html and "<li><b>Drama</b></li>" in html and "2023" not in html


GRADE = {"keywords": [{"term": "terraform", "kind": "must"}, {"term": "monitoring", "kind": "nice"}]}


def _store_grade(job_id):
    with db.connect() as conn:
        conn.execute("UPDATE jobs SET grade = ? WHERE id = ?", (json.dumps(GRADE), job_id))


def test_check_uses_grade_keywords_when_graded(seeded):
    client, job_id, _, _ = seeded
    _store_grade(job_id)
    out = client.post(f"/jobs/{job_id}/check", json={
        "text": "terraform", "bullets": [], "roles": {"role_1": "Ran Kubernetes and caching", "role_2": "Terraform monitoring"}}).json()
    assert out["role_hits"] == {"role_1": 0, "role_2": 2}
    assert out["ats"]["score"] == 67 and out["ats"]["missing"] == ["monitoring"]


def test_tailor_ranks_bullets_by_grade_keywords(seeded):
    client, job_id, role, bullet = seeded
    _store_grade(job_id)
    texts = ["Used kubernetes and caching.", "Set up kubernetes caching.", "Ran caching for kubernetes.", "Wrote terraform."]
    llm_out = json.dumps({"bullets": [{"text": t, "source_id": bullet} for t in texts]})
    with patch("src.api.tailor.llm.complete", return_value=llm_out):
        out = client.post(f"/jobs/{job_id}/tailor").json()
    included = [b["text"] for b in out["bullets"] if b["included"]]
    assert "Wrote terraform." in included and len(included) == 3


def test_tailor_keeps_a_demoted_skill_up_when_a_stored_must_have_names_it(seeded):
    client, job_id, _, _ = seeded
    ids = [client.post("/skill_pool", json={"name": n, "grp": "Technical", "demote": n == "SQL"}).json()["id"]
           for n in ("SQL", "Python", "Go", "Rust", "Java", "Kotlin")]
    llm_out = json.dumps({"bullets": [], "skills": [f"skill_{i}" for i in ids]})

    def skills():
        with patch("src.api.tailor.llm.complete", return_value=llm_out):
            return client.post(f"/jobs/{job_id}/tailor").json()["skills"]

    assert skills().index(f"skill_{ids[0]}") == 5  # ungraded: SQL pushed below slot 5
    grade = {"requirements": [{"text": "Strong SQL skills", "kind": "must"}], "keywords": [{"term": "go", "kind": "nice"}]}
    with closing(db.connect()) as conn:
        conn.execute("UPDATE jobs SET grade = ? WHERE id = ?", (json.dumps(grade), job_id))
        conn.commit()
    assert skills()[0] == f"skill_{ids[0]}"
