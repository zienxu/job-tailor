"""Tailoring core: strips contacts, prompts Groq, fact-checks the result.

Profile shape: {"contacts": {"name", "email", "phone"},
                "roles": [{"id", "company", "title"}],
                "bullets": [{"id", "role_id", "text"}],
                "stories": [{"id", "role_id", "text"}],
                "skill_pool": [{"id", "name", "aliases", "is_default", "demote"}]}
"""
import json

from src.api import llm
from src.api.ats import extract_terms, hits
from src.api.factcheck import check_bullet

SYSTEM_PROMPT = (
    "You tailor a resume to a job description using ONLY the given source bullets "
    "and stories. Sources are grouped by role. For every role write at most 3 bullets, the "
    "ones most relevant to the job, and at least 1; fewer than 3 is fine, never pad. "
    "Set source_id to the cited bullet's id exactly as given; you may also write bullets "
    "drawn from a role's own stories, citing the story id; a story bullet summarises the story in one "
    "resume-style sentence of at most 30 words, never copies it. Do not invent facts, numbers, "
    "companies, or titles not present in the cited source. "
    "Sources may mark bold with **double asterisks**; keep the ** around the same words where they survive in your bullet. "
    "Also pick 12 to 14 skills for the resume's one-line Skills section from the given skill_pool, most relevant "
    "to the job first, as ids exactly as given. Never name a skill that is not in the pool. Match a job term to a "
    "skill only by its name or its listed aliases. "
    'Respond with JSON only: {"bullets": [{"text": "...", "source_id": "..."}], "skills": ["skill_1"]}'
)

SKILLS_MIN, SKILLS_MAX = 12, 14  # shortcut: 14 is a guess for two lines; lower SKILLS_MAX if the PDF wraps further
DEMOTED_BELOW = 5  # a demoted skill (SQL) stays out of the first five unless the job requires it


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
    pool = [{"id": p["id"], "name": p["name"], "aliases": p["aliases"]} for p in profile.get("skill_pool", [])]
    return json.dumps({"job": job_text, "roles": roles, "skill_pool": pool})


def pick_skills(ids, pool: list[dict], required: list[str]) -> list[str]:
    """Order the LLM's picks, dropping unknown ids and dupes, padding from defaults (or all defaults when
    nothing usable came back), capping, demoting."""
    by_id = {p["id"]: p for p in pool}
    picked = list(dict.fromkeys(i for i in (ids if isinstance(ids, list) else []) if isinstance(i, str) and i in by_id))
    defaults = [p["id"] for p in pool if p["is_default"] and p["id"] not in picked]
    picked += defaults[:max(0, SKILLS_MIN - len(picked))] if picked else defaults  # no usable picks: every default
    picked = picked[:SKILLS_MAX]
    musts = "\n".join(required)  # a posting term matches only a skill's name or one of its listed aliases
    bad = [i for i in picked[:DEMOTED_BELOW] if by_id[i]["demote"]
           and not hits([by_id[i]["name"], *by_id[i]["aliases"].split(",")], musts)]
    rest = [i for i in picked if i not in bad]
    picked = rest[:DEMOTED_BELOW] + bad + rest[DEMOTED_BELOW:]
    return picked


def _flag_all_missing(sources: dict[str, str]) -> list[dict]:
    return [
        {"text": "", "source_id": None, "flags": ["unparseable_response"], "fallback": False,
         "included": True}
    ]


def tailor(job_text: str, profile: dict, keywords: list[dict] | None = None, required: list[str] = ()) -> dict:
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
        return {"contacts": contacts, "bullets": _flag_all_missing(sources),
                "skills": pick_skills(None, stripped.get("skill_pool", []), list(required))}

    out = []
    for b in bullets:
        text = b.get("text", "") if isinstance(b, dict) else ""
        source_id = b.get("source_id") if isinstance(b, dict) else None
        flags = check_bullet(text, source_id, sources)
        # Bullets without a valid citation stay included, so the review gate still sees their flag.
        out.append({"text": text, "source_id": source_id, "flags": flags, "fallback": False, "included": True})

    terms = extract_terms(job_text, keywords)

    role_of = {s["id"]: s["role_id"] for s in stripped.get("bullets", []) + stripped.get("stories", [])}
    cited = {b["source_id"] for b in out if isinstance(b["source_id"], str)}
    # Keep every saved bullet, but include only the best 3 LLM bullets per role (unflagged, then
    # job-term hits, then output order), or an uncited role's first saved bullet. Never pad.
    for r in stripped.get("roles", []):
        mine = [b for b in out if isinstance(b["source_id"], str) and role_of.get(b["source_id"]) == r["id"]]
        for i, b in enumerate(sorted(mine, key=lambda b: (bool(b["flags"]), -hits(terms, b["text"])))):
            b["included"] = i < 3
        uncited = [b for b in stripped.get("bullets", []) if b["role_id"] == r["id"] and b["id"] not in cited]
        for i, b in enumerate(uncited):
            out.append({"text": b["text"], "source_id": b["id"], "flags": check_bullet(b["text"], b["id"], sources),
                        "fallback": True, "included": not mine and i == 0})
    return {"contacts": contacts, "bullets": out,
            "skills": pick_skills(parsed.get("skills") if isinstance(parsed, dict) else None,
                                  stripped.get("skill_pool", []), list(required))}
