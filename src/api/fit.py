"""Fit grade before tailoring: the LLM lists requirements and keywords, code scores them.
Contacts are never sent. A bad response raises ValueError; nothing is half-graded."""
import json
from decimal import ROUND_HALF_UP, Decimal

from src.api import llm
from src.api.tailor import strip_contacts

SYSTEM_PROMPT = (
    "You grade how well a candidate's saved profile fits a job. List the job's requirements; for each give "
    "kind (must or nice), hard_gate (true only for a non-negotiable must-have such as a required degree, "
    "licence, clearance or work authorisation), status (met, partial or missing) judged ONLY from the profile, "
    "and evidence_ids: the profile ids (role, bullet, story, skill or fact) that show it, exactly as given. "
    "Facts are the candidate's own statements about work authorisation, citizenship, availability and "
    "experience level; use them for such requirements. "
    "Also list 10 to 25 ATS keywords from the job, each tagged must or nice. "
    "Also give seniority_fit: under, match or over, comparing the level the job asks for with the candidate's "
    "experience level, and summary: one plain sentence on how well the candidate fits overall. "
    "Respond with JSON only: "
    '{"requirements": [{"text": "...", "kind": "must", "hard_gate": false, "status": "met", '
    '"evidence_ids": ["bullet_1"]}], "keywords": [{"term": "...", "kind": "must"}], '
    '"seniority_fit": "match", "summary": "..."}'
)

WEIGHT = {"must": 2, "nice": 1}
VALUE = {"met": 1, "partial": 0.5, "missing": 0}
SENIORITY = ("under", "match", "over")


def _valid(parsed) -> bool:
    reqs, kws = (parsed.get("requirements"), parsed.get("keywords")) if isinstance(parsed, dict) else (None, None)
    return (
        isinstance(reqs, list) and reqs and isinstance(kws, list)
        and parsed.get("seniority_fit") in SENIORITY and isinstance(parsed.get("summary"), str)
        and all(isinstance(r, dict) and isinstance(r.get("text"), str) and r.get("kind") in WEIGHT
                and isinstance(r.get("hard_gate"), bool) and r.get("status") in VALUE
                and isinstance(r.get("evidence_ids"), list) for r in reqs)
        and all(isinstance(k, dict) and isinstance(k.get("term"), str) and k.get("kind") in WEIGHT for k in kws)
    )


def band(score: float, gated: bool = False) -> str:
    b = "Apply" if score >= 3.8 else "Stretch" if score >= 3.0 else "Skip"
    return "Stretch" if gated and b == "Apply" else b


def grade(job_text: str, profile: dict) -> dict:
    _, stripped = strip_contacts(profile)
    known = {x["id"] for k in ("roles", "bullets", "stories", "skills", "facts") for x in stripped.get(k, [])}
    raw = llm.complete(SYSTEM_PROMPT, json.dumps({"job": job_text, "profile": stripped}))
    parsed = json.loads(raw)
    if not _valid(parsed):
        raise ValueError("grade response has the wrong shape")
    reqs = []
    for r in parsed["requirements"]:
        ids = [i for i in r["evidence_ids"] if i in known]
        # Fail closed like the tailor fact check: a claim with no real saved item behind it is missing.
        status = r["status"] if ids else "missing"
        reqs.append({"text": r["text"], "kind": r["kind"], "hard_gate": r["hard_gate"],
                     "status": status, "evidence_ids": ids})
    coverage = sum(WEIGHT[r["kind"]] * VALUE[r["status"]] for r in reqs) / sum(WEIGHT[r["kind"]] for r in reqs)
    # Half-up, not Python's half-even round(), which turns 3.25 into 3.2.
    score = float(Decimal(str(1 + 4 * coverage)).quantize(Decimal("0.1"), ROUND_HALF_UP))
    gated = any(r["kind"] == "must" and r["status"] == "missing" for r in reqs)
    return {"score": score, "band": band(score, gated), "requirements": reqs,
            "keywords": [{"term": k["term"], "kind": k["kind"]} for k in parsed["keywords"]],
            "seniority_fit": parsed["seniority_fit"], "summary": parsed["summary"].strip()}
