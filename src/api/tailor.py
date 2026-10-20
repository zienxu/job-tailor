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
    "Sources are grouped by role; write at least 1 bullet for every role. "
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
    items = profile.get("bullets", []) + profile.get("stories", [])
    roles = [{**r, "sources": {s["id"]: s["text"] for s in items if s["role_id"] == r["id"]}}
             for r in profile.get("roles", [])]
    return json.dumps({"job": job_text, "roles": roles})


def _flag_all_missing(sources: dict[str, str]) -> list[dict]:
    return [
        {"text": "", "source_id": None, "flags": ["unparseable_response"], "fallback": False}
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
        out.append({"text": text, "source_id": source_id, "flags": flags, "fallback": False})

    # Keep every role: an uncited role gets its first 2 saved bullets (already in position order), unchanged.
    role_of = {s["id"]: s["role_id"] for s in stripped.get("bullets", []) + stripped.get("stories", [])}
    covered = {role_of.get(b["source_id"]) for b in out if isinstance(b["source_id"], str)}
    for r in stripped.get("roles", []):
        if r["id"] in covered:
            continue
        for b in [b for b in stripped.get("bullets", []) if b["role_id"] == r["id"]][:2]:
            out.append({"text": b["text"], "source_id": b["id"],
                        "flags": check_bullet(b["text"], b["id"], sources), "fallback": True})
    return {"contacts": contacts, "bullets": out}
