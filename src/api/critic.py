"""Devil's-advocate critic: a second Groq call that returns suggestions only.
It never edits the resume. Contacts are never sent."""
import json

from src.api import llm

KEYS = ("unmet_must_haves", "weak_bullets", "missing_keywords", "overstated_claims")

SYSTEM_PROMPT = (
    "You are a skeptical hiring manager reviewing resume bullets against a job. "
    "Do not rewrite anything; only point out problems. Respond with JSON only: "
    '{"unmet_must_haves": ["..."], '
    '"weak_bullets": [{"text": "...", "reason": "..."}], '
    '"missing_keywords": ["..."], '
    '"overstated_claims": [{"text": "...", "reason": "..."}], '
    '"readiness": {"verdict": "ready" or "needs_work", "reason": "..."}}. '
    "readiness is your one-line call on whether this resume is ready to send for this job."
)


def _failed(error: str) -> dict:
    return {**{k: [] for k in KEYS}, "readiness": None, "error": error}


def _valid(parsed: dict) -> bool:
    def is_note(i):
        return isinstance(i, dict) and isinstance(i.get("text"), str) and isinstance(i.get("reason"), str)

    readiness = parsed.get("readiness")
    return (
        isinstance(readiness, dict)
        and readiness.get("verdict") in ("ready", "needs_work")
        and isinstance(readiness.get("reason"), str)
        and all(isinstance(parsed.get(k), list) for k in KEYS)
        and all(isinstance(i, str) for k in ("unmet_must_haves", "missing_keywords") for i in parsed[k])
        and all(is_note(i) for k in ("weak_bullets", "overstated_claims") for i in parsed[k])
    )


def critique(job_text: str, resume: dict) -> dict:
    bullets = [b["text"] for b in resume.get("bullets", [])]
    user_prompt = json.dumps({"job": job_text, "bullets": bullets})
    try:
        raw = llm.complete(SYSTEM_PROMPT, user_prompt)
    except Exception:
        return _failed("llm_call_failed")
    try:
        parsed = json.loads(raw)
        if not _valid(parsed):
            raise ValueError("critic response has the wrong shape")
    except Exception:
        return _failed("unparseable_response")
    readiness = {"verdict": parsed["readiness"]["verdict"], "reason": parsed["readiness"]["reason"]}
    return {**{k: parsed[k] for k in KEYS}, "readiness": readiness}
