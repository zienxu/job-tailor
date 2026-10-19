import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from src.api.fetch_job import fetch_job
from src.api.main import app

GREENHOUSE = {
    "title": "Backend Engineer",
    "company_name": "Acme",
    "content": "&lt;p&gt;Build &lt;strong&gt;Python&lt;/strong&gt; APIs &amp;amp; services.&lt;/p&gt;"
               "&lt;ul&gt;&lt;li&gt;FastAPI&lt;/li&gt;&lt;li&gt;SQLite&lt;/li&gt;&lt;/ul&gt;",
}
LEVER = {
    "text": "Data Engineer",
    "descriptionPlain": "Join our data team.",
    "lists": [{"text": "Requirements", "content": "<li>Spark</li><li>Airflow &amp; dbt</li>"}],
    "additionalPlain": "Remote friendly.",
}
LEVER_URL = "https://jobs.lever.co/acme/0a1b2c3d-4e5f-6789-abcd-ef0123456789"


def _mock(payload):
    return patch("src.api.fetch_job.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))


def test_greenhouse_link_returns_text():
    with _mock(GREENHOUSE) as m:
        job = fetch_job("https://job-boards.greenhouse.io/acme/jobs/4012345")
    assert m.call_args.args[0] == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/4012345"
    assert "Build Python APIs & services." in job["text"]
    assert "FastAPI\nSQLite" in job["text"]
    assert "<" not in job["text"]
    assert (job["title"], job["company"]) == ("Backend Engineer", "Acme")


@pytest.mark.parametrize("suffix", ["", "/apply"])
def test_lever_link_returns_text(suffix):
    with _mock(LEVER) as m:
        job = fetch_job(LEVER_URL + suffix)
    assert m.call_args.args[0] == "https://api.lever.co/v0/postings/acme/0a1b2c3d-4e5f-6789-abcd-ef0123456789"
    for part in ["Join our data team.", "Requirements", "Spark", "Airflow & dbt", "Remote friendly."]:
        assert part in job["text"]
    assert (job["title"], job["company"]) == ("Data Engineer", "acme")


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/123456",
    "http://boards.greenhouse.io/acme/jobs/1",
    "https://boards.greenhouse.io.evil.com/acme/jobs/1",
    "https://boards.greenhouse.io/acme/jobs/notanumber",
    "https://boards.greenhouse.io/../jobs/1",
    "https://jobs.lever.co/acme",
    "https://jobs.lever.co/acme/apply",
    "https://boards.greenhouse.io/acmé/jobs/١٢",
    "not a url",
])
def test_other_links_refused(url):
    with _mock({}) as m, pytest.raises(ValueError, match="paste the text"):
        fetch_job(url)
    m.assert_not_called()


def test_api_fetch():
    client = TestClient(app)
    with _mock(LEVER):
        r = client.post("/jobs/fetch", json={"url": LEVER_URL})
    assert r.status_code == 200 and "Spark" in r.json()["text"]

    r = client.post("/jobs/fetch", json={"url": "https://www.linkedin.com/jobs/view/123456"})
    assert r.status_code == 422 and r.json()["detail"] == "paste the text"

    with patch("src.api.fetch_job.urlopen", side_effect=OSError("down")):
        r = client.post("/jobs/fetch", json={"url": LEVER_URL})
    assert r.status_code == 502

    with patch("src.api.fetch_job.urlopen", side_effect=HTTPError(LEVER_URL, 404, "Not Found", None, None)):
        r = client.post("/jobs/fetch", json={"url": LEVER_URL})
    assert r.status_code == 404 and r.json()["detail"] == "job not found"
