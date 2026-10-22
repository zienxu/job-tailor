import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from src.api.fetch_job import _CheckedRedirects, _fetch_page, fetch_job
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


LINKEDIN_URL = "https://www.linkedin.com/jobs/view/123456"
POSTING = {"@context": "https://schema.org", "@type": "JobPosting", "title": "Data Analyst",
           "hiringOrganization": {"@type": "Organization", "name": "Acme"},
           "description": "&lt;p&gt;Use &lt;strong&gt;SQL&lt;/strong&gt; daily.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Tableau&lt;/li&gt;&lt;/ul&gt;"}
PAGE = f'<html><head><script type="application/ld+json">{json.dumps(POSTING)}</script></head><body>nav</body></html>'


def _page(html):
    return patch("src.api.fetch_job._fetch_page", return_value=html)


def test_any_page_reads_its_job_posting_data():
    with _page(PAGE):
        job = fetch_job(LINKEDIN_URL)
    assert job == {"text": "Use SQL daily.\nTableau", "title": "Data Analyst", "company": "Acme", "link": LINKEDIN_URL}


def test_any_page_in_a_graph_list():
    graph = {"@graph": [{"@type": "WebPage"}, {**POSTING, "@type": ["JobPosting"]}]}
    with _page(f'<script type="application/ld+json">{json.dumps(graph)}</script>'):
        assert fetch_job("https://careers.example.com/1")["title"] == "Data Analyst"


def test_any_page_without_posting_data_falls_back_to_visible_text():
    body = "<p>" + "We need a Kotlin developer. " * 10 + "</p>"
    with _page(f"<html><head><title>x</title><style>p{{}}</style></head><body><script>var a=1</script>{body}</body></html>"):
        job = fetch_job("https://careers.example.com/2")
    assert job["text"].startswith("We need a Kotlin developer.") and "var a" not in job["text"] and "p{}" not in job["text"]


def test_login_wall_or_empty_page_is_refused():
    with _page("<html><body>Sign in to see this job</body></html>"), pytest.raises(ValueError, match="paste the text"):
        fetch_job(LINKEDIN_URL)


@pytest.mark.parametrize("url", [
    "http://boards.greenhouse.io/acme/jobs/1",
    "http://www.linkedin.com/jobs/view/1",
    "https://localhost/jobs/1",
    "https://127.0.0.1/jobs/1",
    "https://10.0.0.5/jobs/1",
    "https://192.168.1.1/",
    "https://[::1]/",
    "https://[::ffff:127.0.0.1]/",
    "https://[64:ff9b::7f00:1]/",
    "file:///etc/passwd",
    "not a url",
])
def test_local_or_non_https_links_refused(url):
    with _mock({}) as m, pytest.raises(ValueError, match="paste the text"):
        fetch_job(url)
    m.assert_not_called()


def test_redirect_to_a_private_address_is_refused():
    with pytest.raises(ValueError, match="paste the text"):
        _CheckedRedirects().redirect_request(None, None, 302, "Found", {}, "https://127.0.0.1/admin")


def test_api_fetch():
    client = TestClient(app)
    with _mock(LEVER):
        r = client.post("/jobs/fetch", json={"url": LEVER_URL})
    assert r.status_code == 200 and "Spark" in r.json()["text"]

    with _page(PAGE):
        r = client.post("/jobs/fetch", json={"url": LINKEDIN_URL})
    assert r.status_code == 200 and r.json()["company"] == "Acme"

    r = client.post("/jobs/fetch", json={"url": "https://127.0.0.1/jobs/1"})
    assert r.status_code == 422 and r.json()["detail"] == "paste the text"

    with patch("src.api.fetch_job.urlopen", side_effect=OSError("down")):
        r = client.post("/jobs/fetch", json={"url": LEVER_URL})
    assert r.status_code == 502

    with patch("src.api.fetch_job.urlopen", side_effect=HTTPError(LEVER_URL, 404, "Not Found", None, None)):
        r = client.post("/jobs/fetch", json={"url": LEVER_URL})
    assert r.status_code == 404 and r.json()["detail"] == "job not found"


@pytest.mark.parametrize("graph", [None, POSTING])
def test_odd_graph_shapes_dont_crash(graph):
    page = f'<script type="application/ld+json">{json.dumps({"@graph": graph})}</script>' + "<p>" + "Job text here. " * 20 + "</p>"
    with _page(page):
        job = fetch_job("https://careers.example.com/3")
    assert job["title"] == ("Data Analyst" if graph else "")


def test_empty_description_falls_back_to_visible_text():
    page = f'<script type="application/ld+json">{json.dumps({**POSTING, "description": "  "})}</script>' + "<p>" + "Visible job ad. " * 20 + "</p>"
    with _page(page):
        assert fetch_job("https://careers.example.com/4")["text"].startswith("Visible job ad.")


def test_huge_page_text_is_capped():
    with _page("<p>" + "word " * 30_000 + "</p>"):
        assert len(fetch_job("https://careers.example.com/5")["text"]) == 50_000


def test_unknown_charset_decodes_as_utf8():
    resp = io.BytesIO("Café job".encode())
    resp.headers = type("H", (), {"get_content_charset": lambda self: "utf8mb4"})()
    opener = type("O", (), {"open": lambda self, req, timeout: resp})()
    with patch("src.api.fetch_job._check_public"), patch("src.api.fetch_job.build_opener", return_value=opener):
        assert _fetch_page("https://careers.example.com/6") == "Café job"
