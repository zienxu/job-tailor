import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import db
from src.api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    return TestClient(app)


def _job(client):
    return client.post("/jobs", json={"text": "Need Python"}).json()["id"]


def _version(client, job_id, content=None):
    return client.post(f"/jobs/{job_id}/versions", json={"content": content or {"bullets": []}}).json()["id"]


def test_mark_applied_records_version(client):
    job_id = _job(client)
    _version(client, job_id)
    v2 = _version(client, job_id)
    r = client.put(f"/jobs/{job_id}", json={"company": "Acme", "status": "applied",
                                            "applied_at": "2026-10-21", "version_id": v2})
    assert r.status_code == 200, r.text
    [job] = client.get("/jobs").json()
    assert (job["company"], job["status"], job["applied_at"], job["version_id"]) == ("Acme", "applied", "2026-10-21", v2)
    assert [v["id"] for v in job["versions"]] == [v2 - 1, v2]


def test_new_job_defaults_to_saved(client):
    v = _version(client, _job(client))
    [job] = client.get("/jobs").json()
    assert (job["status"], job["version_id"], [x["id"] for x in job["versions"]]) == ("saved", None, [v])


def test_job_without_versions_is_not_listed(client):
    _job(client)  # Tailor makes a job row; it shows only after "Save in tracker"
    assert client.get("/jobs").json() == []


def test_applied_needs_own_version(client):
    b = _job(client)
    vb = _version(client, b)
    a = _job(client)
    assert client.put(f"/jobs/{a}", json={"status": "applied"}).status_code == 422
    assert client.put(f"/jobs/{a}", json={"status": "applied", "version_id": vb}).status_code == 422
    assert client.put(f"/jobs/{a}", json={"status": "bogus"}).status_code == 422
    assert client.get(f"/jobs/{a}").json()["status"] == "saved"


def test_partial_update_keeps_other_fields(client):
    job_id = _job(client)
    v = _version(client, job_id)
    client.put(f"/jobs/{job_id}", json={"status": "applied", "version_id": v})
    assert client.put(f"/jobs/{job_id}", json={"notes": "called back"}).status_code == 200
    job = client.get(f"/jobs/{job_id}").json()
    assert (job["status"], job["version_id"], job["notes"]) == ("applied", v, "called back")


def test_delete_job_removes_versions(client):
    job_id = _job(client)
    v = _version(client, job_id)
    assert client.delete(f"/jobs/{job_id}").status_code == 204
    assert client.get("/jobs").json() == []
    assert client.get(f"/versions/{v}/pdf").status_code == 404
    assert client.delete(f"/jobs/{job_id}").status_code == 404


def test_rebuild_pdf_from_stored_resume(client):
    job_id = _job(client)
    v = _version(client, job_id, {"bullets": [], "resume": {"name": "Ada", "experience": []}})
    with patch("src.api.main.pdf.render_pdf", return_value=b"%PDF-fake") as render:
        r = client.get(f"/versions/{v}/pdf")
    assert r.status_code == 200 and r.content == b"%PDF-fake"
    assert r.headers["content-type"] == "application/pdf"
    assert render.call_args.args[0]["name"] == "Ada"


def test_old_version_without_resume_cannot_rebuild(client):
    v = _version(client, _job(client))
    assert client.get(f"/versions/{v}/pdf").status_code == 409


def test_old_jobs_table_migrates(client):
    old = sqlite3.connect(db.DB_PATH)
    old.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL DEFAULT '',"
                " title TEXT NOT NULL DEFAULT '', link TEXT NOT NULL DEFAULT '', text TEXT NOT NULL,"
                " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    old.execute("INSERT INTO jobs (text) VALUES ('old job')")
    old.commit()
    old.close()
    job = client.get("/jobs/1").json()
    assert (job["text"], job["status"], job["notes"], job["version_id"]) == ("old job", "saved", "", None)


def test_bad_stored_resume_is_409_not_500(client):
    v = _version(client, _job(client), {"resume": {"experience": "not a list"}})
    assert client.get(f"/versions/{v}/pdf").status_code == 409


def test_applied_at_must_be_a_date(client):
    job_id = _job(client)
    assert client.put(f"/jobs/{job_id}", json={"applied_at": "last Tuesday"}).status_code == 422
    assert client.put(f"/jobs/{job_id}", json={"applied_at": ""}).status_code == 200


def test_tailor_drops_other_unsaved_jobs(client):
    kept = _job(client)
    _version(client, kept)
    unsaved = _job(client)
    latest = _job(client)
    assert client.get(f"/jobs/{unsaved}").status_code == 200  # creating a job (e.g. to grade it) deletes nothing
    out = json.dumps({"bullets": [{"text": "x", "source_id": None}]})
    with patch("src.api.tailor.llm.complete", return_value=out):
        assert client.post(f"/jobs/{latest}/tailor").status_code == 200
    assert client.get(f"/jobs/{unsaved}").status_code == 404
    assert client.get(f"/jobs/{kept}").status_code == 200
    assert client.get(f"/jobs/{latest}").status_code == 200


PDF = b"%PDF-1.4\n" + bytes(range(256)) + b"\n%%EOF"


def _upload(client, job_id, data=PDF, name="cv.pdf"):
    return client.post(f"/jobs/{job_id}/versions/upload", files={"file": (name, data, "application/pdf")})


def test_upload_adds_version_and_downloads_identical_bytes(client):
    job_id = _job(client)
    r = _upload(client, job_id)
    assert r.status_code == 201, r.text
    assert r.json()["uploaded"] is True and "pdf" not in r.json()
    assert client.get(f"/versions/{r.json()['id']}/pdf").content == PDF
    [job] = client.get("/jobs").json()
    assert [v["uploaded"] for v in job["versions"]] == [True]


def test_upload_appends_and_keeps_grade(client):
    job_id = _job(client)
    sqlite3.connect(db.DB_PATH).execute("UPDATE jobs SET grade = '{}' WHERE id = ?", (job_id,)).connection.commit()
    a, b = _upload(client, job_id).json()["id"], _upload(client, job_id).json()["id"]
    assert b > a
    assert client.get(f"/jobs/{job_id}").json()["grade"] == {}


def test_upload_rejects_non_pdf_oversize_and_missing_job(client):
    job_id = _job(client)
    assert _upload(client, job_id, b"hello").status_code == 422
    assert _upload(client, job_id, b"%PDF" + b"0" * (5 * 1024 * 1024)).status_code == 413
    assert _upload(client, 999).status_code == 404
    assert client.get("/jobs").json() == []  # nothing was saved


def test_old_version_without_pdf_still_rebuilds_and_latest_skips_uploads(client):
    job_id = _job(client)
    v = _version(client, job_id)
    _upload(client, job_id)
    assert client.get(f"/versions/{v}/pdf").status_code == 409  # still the rebuild path
    assert client.get("/versions/latest").json()["id"] == v


def test_old_versions_table_gets_pdf_column(client):
    old = sqlite3.connect(db.DB_PATH)
    old.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL)")
    old.execute("INSERT INTO jobs (text) VALUES ('old job')")
    old.execute("CREATE TABLE resume_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL,"
                " content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    old.commit()
    old.close()
    assert _upload(client, 1).status_code == 201


def _letter(client, job_id, data=PDF, name="cl.pdf"):
    return client.post(f"/jobs/{job_id}/cover-letters", files={"file": (name, data, "application/pdf")})


def test_cover_letter_round_trips_lists_and_appends(client):
    job_id = _job(client)  # no resume version: the letter alone puts the job in the tracker
    a, b = _letter(client, job_id), _letter(client, job_id)
    assert a.status_code == 201 and "pdf" not in a.json()
    assert client.get(f"/cover-letters/{a.json()['id']}/pdf").content == PDF
    [job] = client.get("/jobs").json()
    assert [c["id"] for c in job["cover_letters"]] == [a.json()["id"], b.json()["id"]]
    assert job["versions"] == [] and "pdf" not in job["cover_letters"][0]


def test_cover_letter_rejects_bad_files_and_cascades(client):
    job_id = _job(client)
    assert _letter(client, job_id, b"hello").status_code == 422
    assert _letter(client, job_id, b"%PDF" + b"0" * (5 * 1024 * 1024)).status_code == 413
    assert _letter(client, 999).status_code == 404
    assert client.get("/jobs").json() == []
    cid = _letter(client, job_id).json()["id"]
    client.delete(f"/jobs/{job_id}")
    assert client.get(f"/cover-letters/{cid}/pdf").status_code == 404


def test_tailor_keeps_job_with_only_a_cover_letter(client):
    kept, other = _job(client), _job(client)
    _letter(client, kept)
    with patch("src.api.main.tailor", return_value={"bullets": [], "skills": [], "summary": ""}):
        client.post(f"/jobs/{other}/tailor")
    assert client.get(f"/jobs/{kept}").status_code == 200
