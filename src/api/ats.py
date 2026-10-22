"""Local ATS keyword estimate: stemmed job terms plus repeated 2-word phrases, weighted by job section.

shortcut: required/preferred headings are found with a regex on short lines; real job ads vary,
so check accuracy on real jobs before trusting the weights more.
"""
import re
from collections import Counter
from functools import lru_cache

import snowballstemmer

LABEL = "local estimate"

# Keeps tech tokens whole: ci/cd, c++, c#, node.js, cross-team.
TOKEN_RE = re.compile(r"[a-z0-9+#][a-z0-9+#./-]*")
# A 2-word phrase never spans a list separator, so "Python, SQL" is not a pair.
SEGMENT_RE = re.compile(r"[\n,;:()]|\.\s")
REQUIRED = re.compile(r"\b(requirements?|must[- ]haves?|qualifications?)\b")
PREFERRED = re.compile(r"\b(preferred|nice[- ]to[- ]haves?)\b")
STEMMER = snowballstemmer.stemmer("english")

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


def _stem(t: str) -> str:
    return STEMMER.stemWord(t) if t.isalpha() else t  # c++, ci/cd, node.js stay whole


def _is_term(t: str) -> bool:
    return len(t) >= 2 and t not in STOPWORDS and bool(re.search(r"[a-z]", t))  # skip "10", "5+"


def _heading(line: str) -> tuple[int | None, str]:
    """(new weight or None, text left for terms). 2 under Requirements/Must have/Qualifications,
    1 under Preferred/Nice to have or any other short "X:" title line. Inline "Requirements: X" keeps X."""
    s = line.strip().lower()
    if len(s.split(":", 1)[0].split()) <= 5:
        for regex, weight in ((PREFERRED, 1), (REQUIRED, 2)):
            if regex.search(s.split(":", 1)[0]):
                return weight, PREFERRED.sub(" ", REQUIRED.sub(" ", s))
        if s.endswith(":") and not s.startswith(("-", "*", "•")):  # "- Strong communication skills:" is a bullet
            return 1, ""
    return None, s


def _terms(job_text: str) -> dict[str, tuple[str, int]]:
    """stem key -> (first surface form, highest weight it appears under)."""
    words, pairs, pair_count = {}, {}, Counter()

    def add(into, key, display, weight):
        old = into.get(key)
        into[key] = (old[0], max(old[1], weight)) if old else (display, weight)

    weight = 1
    for line in job_text.splitlines():
        heading, line = _heading(line)
        if heading is not None:
            weight = heading
        for seg in SEGMENT_RE.split(line):
            toks = _tokens(seg)
            for t in toks:
                if _is_term(t):
                    add(words, _stem(t), t, weight)
            for a, b in zip(toks, toks[1:]):
                if _is_term(a) and _is_term(b):
                    key = f"{_stem(a)} {_stem(b)}"
                    pair_count[key] += 1
                    add(pairs, key, f"{a} {b}", weight)
    return words | {k: v for k, v in pairs.items() if pair_count[k] >= 2}


def _keys(text: str) -> set[str]:
    """Every 1- to 4-word stem run; 3-4 word runs exist only so grade keywords like
    "large language models" can match. shortcut: a 5+ word keyword never matches."""
    keys = set()
    for seg in SEGMENT_RE.split(text.replace("**", "")):
        stems = [_stem(t) for t in _tokens(seg)]
        for n in range(1, 5):
            keys.update(" ".join(stems[i:i + n]) for i in range(len(stems) - n + 1))
    return keys


def _job_terms(job_text: str, keywords: list[dict] | None = None) -> dict[str, tuple[str, int]]:
    """The graded job's keywords (must 2, nice 1) when given, else the job's own terms."""
    out = {}
    for k in keywords or []:
        if not (isinstance(k, dict) and isinstance(k.get("term"), str)):
            continue  # a malformed stored keyword is skipped, never a 500
        key, weight = _key(k["term"]), 2 if k.get("kind") == "must" else 1
        old = out.get(key)
        if key:
            out[key] = (old[0], max(old[1], weight)) if old else (k["term"], weight)
    return out or _terms(job_text)


def extract_terms(job_text: str, keywords: list[dict] | None = None) -> list[str]:
    return [display for display, _ in _job_terms(job_text, keywords).values()]


@lru_cache(maxsize=4096)
def _key(term: str) -> str:
    return " ".join(_stem(t) for t in _tokens(term))


def hits(terms: list[str], text: str) -> int:
    """How many job terms appear in text, matched like score() (unweighted)."""
    keys = _keys(text)
    return sum(_key(term) in keys for term in terms)


def score(job_text: str, resume_text: str, keywords: list[dict] | None = None) -> dict:
    terms = _job_terms(job_text, keywords)
    keys = _keys(resume_text)
    matched = [d for k, (d, _) in terms.items() if k in keys]
    missing = [d for k, (d, _) in terms.items() if k not in keys]
    total = sum(w for _, w in terms.values())
    got = sum(w for k, (_, w) in terms.items() if k in keys)
    pct = round(100 * got / total) if total else 0
    return {"label": LABEL, "score": pct, "matched": matched, "missing": missing}
