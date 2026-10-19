"""Tailoring core: strips contacts, prompts Groq, fact-checks the result.

Profile shape: {"contacts": {"name", "email", "phone"},
                "roles": [{"id", "company", "title"}],
                "bullets": [{"id", "role_id", "text"}],
                "stories": [{"id", "role_id", "text"}]}
"""
import json

from src.api import llm
from src.api.factcheck import check_bullet

SYSTEM_PROMPT = (
    "You tailor a resume to a job description using ONLY the given source bullets "
    "and stories. For every output bullet, pick the single most relevant source and "
    "set source_id to its id exactly as given. Do not invent facts, numbers, "
    "companies, or titles not present in the cited source. "
    'Respond with JSON only: {"bullets": [{"text": "...", "source_id": "..."}]}'
)


def strip_contacts(profile: dict) -> tuple[dict, dict]:
    contacts = profile.get("contacts", {})
    rest = {k: v for k, v in profile.items() if k != "contacts"}
    return contacts, rest


def _sources(profile: dict) -> dict[str, str]:
    sources = {b["id"]: b["text"] for b in profile.get("bullets", [])}
    sources.update({s["id"]: s["text"] for s in profile.get("stories", [])})
    return sources


def build_prompt(job_text: str, profile: dict) -> str:
    return json.dumps({"job": job_text, "sources": _sources(profile)})


def _flag_all_missing(sources: dict[str, str]) -> list[dict]:
    return [
        {"text": "", "source_id": None, "flags": ["unparseable_response"]}
    ]


def tailor(job_text: str, profile: dict) -> dict:
    contacts, stripped = strip_contacts(profile)
    sources = _sources(stripped)
    user_prompt = build_prompt(job_text, stripped)

    # Call failures (network, rate limit, missing key) propagate; only bad responses fail closed.
    raw = llm.complete(SYSTEM_PROMPT, user_prompt)
    try:
        parsed = json.loads(raw)
        bullets = parsed["bullets"]
        if not isinstance(bullets, list):
            raise ValueError("bullets is not a list")
    except Exception:
        return {"contacts": contacts, "bullets": _flag_all_missing(sources)}

    out = []
    for b in bullets:
        text = b.get("text", "") if isinstance(b, dict) else ""
        source_id = b.get("source_id") if isinstance(b, dict) else None
        flags = check_bullet(text, source_id, sources)
        out.append({"text": text, "source_id": source_id, "flags": flags})
    return {"contacts": contacts, "bullets": out}
