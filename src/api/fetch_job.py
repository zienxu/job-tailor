"""Fetch job text: Greenhouse and Lever through their official APIs, any other https page by reading it once
(the user's choice, see DECISIONS.md). Links to this machine or a private network are refused."""
import html
import ipaddress
import json
import re
import socket
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

REFUSED = "paste the text"
MAX_TEXT = 50_000  # characters; a whole page of nav text would otherwise go to the LLM and fail as a vague 502
NAT64 = ipaddress.ip_network("64:ff9b::/96")  # is_global says True, but it can translate to 127.0.0.1

GREENHOUSE_HOSTS = {"boards.greenhouse.io", "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"}
LEVER_API = {"jobs.lever.co": "api.lever.co", "jobs.eu.lever.co": "api.eu.lever.co"}


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=10) as resp:
        return json.loads(resp.read(2_000_000))  # cap size; a truncated body fails to parse


def _check_public(url: str) -> None:
    """Server-side fetch of a user URL: only https to hosts that resolve to public addresses (no SSRF to localhost/LAN)."""
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname:
        raise ValueError(REFUSED)
    try:
        addrs = {a[4][0] for a in socket.getaddrinfo(u.hostname, u.port or 443)}
    except (socket.gaierror, UnicodeError):
        raise ValueError(REFUSED)
    for a in addrs:
        ip = ipaddress.ip_address(a.split("%")[0])
        ip = getattr(ip, "ipv4_mapped", None) or ip  # ::ffff:127.0.0.1 is loopback
        if not ip.is_global or ip in NAT64:
            raise ValueError(REFUSED)


class _CheckedRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_public(newurl)  # a public page must not bounce the fetch onto a private address
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_page(url: str) -> str:
    _check_public(url)
    # shortcut: DNS is checked before the request, not pinned, so a rebinding host could still slip through; fine for a localhost app
    req = Request(url, headers={"User-Agent": "job-tailor (personal use)", "Accept": "text/html"})
    with build_opener(_CheckedRedirects).open(req, timeout=10) as resp:
        raw = resp.read(3_000_000)
        try:
            return raw.decode(resp.headers.get_content_charset() or "utf-8", "replace")
        except LookupError:  # a made-up charset name such as utf8mb4
            return raw.decode("utf-8", "replace")


def _job_posting(page: str) -> dict | None:
    """The schema.org JobPosting most job pages embed for search engines, if any."""
    for block in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        graph = data.get("@graph", [data]) if isinstance(data, dict) else data
        items = graph if isinstance(graph, list) else [graph, data]  # a dict or null @graph; non-dicts are skipped below
        for it in items:
            kind = it.get("@type") if isinstance(it, dict) else None
            if kind == "JobPosting" or isinstance(kind, list) and "JobPosting" in kind:
                return it
    return None


def _any_page(url: str) -> dict:
    page = _fetch_page(url)
    post = _job_posting(page)
    text = _strip_html(html.unescape(post["description"])) if post and isinstance(post.get("description"), str) else ""
    if text:  # an empty description falls through to the visible text and its length check
        org = post.get("hiringOrganization")
        return {"text": text[:MAX_TEXT], "title": str(post.get("title") or ""),
                "company": str(org.get("name") or "") if isinstance(org, dict) else "", "link": url}
    # No structured data: the page's visible text, nav and all; the user trims it in the job text box.
    body = re.sub(r"<(script|style|noscript|svg|head)\b.*?</\1>", "", page, flags=re.S | re.I)
    text = _strip_html(re.sub(r"[ \t]+", " ", body))
    if len(text) < 200:  # a login wall or an empty JS shell, not a job ad
        raise ValueError(REFUSED)
    return {"text": text[:MAX_TEXT], "title": "", "company": "", "link": url}


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

    return _any_page(url)
