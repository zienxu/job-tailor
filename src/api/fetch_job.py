"""Fetch job text from Greenhouse and Lever official APIs. Any other link is refused."""
import html
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen

REFUSED = "paste the text"

GREENHOUSE_HOSTS = {"boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"}
LEVER_API = {"jobs.lever.co": "api.lever.co", "jobs.eu.lever.co": "api.eu.lever.co"}


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=10) as resp:
        return json.loads(resp.read(2_000_000))  # cap size; a truncated body fails to parse


def _strip_html(s: str) -> str:
    s = re.sub(r"<br\s*/?>|</(p|li|h\d|div)>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()


def fetch_job(url: str) -> dict:
    u = urlparse(url.strip())
    host, path = (u.hostname or "").lower(), u.path

    if u.scheme == "https" and host in GREENHOUSE_HOSTS:
        m = re.fullmatch(r"/([\w-]+)/jobs/(\d+)/?", path, re.ASCII)
        if m:
            token, job_id = m.groups()
            data = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}")
            # content is HTML-escaped HTML: unescape once to get tags, then strip them
            return {"text": _strip_html(html.unescape(data.get("content", ""))),
                    "title": data.get("title", ""), "company": data.get("company_name") or token, "link": url}

    if u.scheme == "https" and host in LEVER_API:
        m = re.fullmatch(r"/([\w-]+)/([0-9a-f-]{36})(/apply)?/?", path, re.ASCII)
        if m:
            site, posting = m.group(1), m.group(2)
            data = _get_json(f"https://{LEVER_API[host]}/v0/postings/{site}/{posting}")
            parts = [data.get("descriptionPlain", "")]
            for lst in data.get("lists", []):
                parts += [lst.get("text", ""), _strip_html(lst.get("content", ""))]
            parts.append(data.get("additionalPlain", ""))
            return {"text": "\n\n".join(p.strip() for p in parts if p.strip()),
                    "title": data.get("text", ""), "company": site, "link": url}

    raise ValueError(REFUSED)
