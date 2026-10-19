"""Local ATS keyword estimate: plain term list from the job, unweighted coverage.

shortcut: single tokens only, no stemming or phrases, so "mentor" won't match
"mentored". Add stemming/bigrams if real jobs score too noisily.
"""
import re

LABEL = "local estimate"

# Keeps tech tokens whole: ci/cd, c++, c#, node.js, cross-team.
TOKEN_RE = re.compile(r"[a-z0-9+#][a-z0-9+#./-]*")

STOPWORDS = set("""
a an and are as at be been but by can do for from has have in into is it its
of on or our over per so than that the their them they this to up us was we
were what when which who will with within without you your yours
able about across all also any etc both each more most must new not other
plus such very well work working looking join hiring role team strong
experience years year ability skills including using e.g i.e
""".split())


def _tokens(text: str) -> list[str]:
    return [t.rstrip("./-") for t in TOKEN_RE.findall(text.lower())]


def extract_terms(job_text: str) -> list[str]:
    terms = [
        t for t in _tokens(job_text)
        if len(t) >= 2 and t not in STOPWORDS and re.search(r"[a-z]", t)  # skip "10", "5+"
    ]
    return list(dict.fromkeys(terms))


def score(job_text: str, resume_text: str) -> dict:
    terms = extract_terms(job_text)
    resume_tokens = set(_tokens(resume_text))
    matched = [t for t in terms if t in resume_tokens]
    missing = [t for t in terms if t not in resume_tokens]
    pct = round(100 * len(matched) / len(terms)) if terms else 0
    return {"label": LABEL, "score": pct, "matched": matched, "missing": missing}
