"""Critic: a second Groq call that returns suggestions only.
It never edits the resume. Contacts are never sent."""
import json

from src.api import llm

MAX_ITEMS = 5

SYSTEM_PROMPT = (
    "You are a supportive hiring manager who wants this candidate shortlisted. "
    "Review the resume bullets against the job and flag only what would cost them an interview. "
    "Each bullet comes with its cited source text, the candidate's own saved record; "
    "a claim the source supports is true, so never call it overstated. "
    "Do not rewrite the resume; suggest fixes only. "
    "Return 3 to 5 items ranked by impact, most important first (fewer if that is all there is). "
    "Respond with JSON only: "
    '{"items": [{"bullet": "...", "problem": "...", "fix": "..."}], '
    '"readiness": {"verdict": "ready" or "needs_work", "reason": "..."}}. '
    "readiness is your one-line call on whether this resume is ready to send for this job."
)


def _failed(error: str) -> dict:
    return {"items": [], "readiness": None, "error": error}


def _valid(items, readiness) -> bool:
    return (
        isinstance(readiness, dict)
        and readiness.get("verdict") in ("ready", "needs_work")
        and isinstance(readiness.get("reason"), str)
        and isinstance(items, list)
        and all(isinstance(i, dict) and all(isinstance(i.get(k), str) for k in ("bullet", "problem", "fix"))
                for i in items)
    )


def critique(job_text: str, resume: dict, sources: dict[str, str] | None = None) -> dict:
    sources = sources or {}
    bullets = [{"text": b["text"], "source": sources.get(b.get("source_id"))} for b in resume.get("bullets", [])]
    user_prompt = json.dumps({"job": job_text, "bullets": bullets})
    try:
        raw = llm.complete(SYSTEM_PROMPT, user_prompt)
    except Exception:
        return _failed("llm_call_failed")
    try:
        parsed = json.loads(raw)
        items, readiness = parsed.get("items"), parsed.get("readiness")
        if isinstance(items, list):
            items = items[:MAX_ITEMS]  # ranked, so the first 5 are the top; extras are never inspected
        if not _valid(items, readiness):
            raise ValueError("critic response has the wrong shape")
    except Exception:
        return _failed("unparseable_response")
    return {
        "items": [{k: i[k] for k in ("bullet", "problem", "fix")} for i in items],
        "readiness": {"verdict": readiness["verdict"], "reason": readiness["reason"]},
    }
