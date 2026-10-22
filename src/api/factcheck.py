"""Fact-check: flag output bullets with missing/invalid citations, or claims
(numbers, proper nouns like companies/titles) not present in the cited source text.

shortcut: proper-noun detection is a plain capitalized-word regex, not NER, so a
paraphrased verb can false-positive and an all-lowercase invented fact can slip
through. Upgrade to spaCy NER if false positives show up on real Groq output.
"""
import re

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")
PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
# A sentence break is end punctuation then a capital, so "e.g. caching" stays one sentence.
# shortcut: "U.S. Army" or "Inc. Acme" also count as a break (a false story_too_long the user can keep);
# use an abbreviation list if real bullets trip it.
SENTENCE_BREAK_RE = re.compile(r"[.!?]\s+[A-Z]")
STORY_MAX_WORDS = 30


def check_bullet(text: str, source_id: str | None, sources: dict[str, str]) -> list[str]:
    if not source_id:
        return ["missing_citation"]
    if not isinstance(source_id, str) or source_id not in sources:
        return ["invalid_citation_id"]

    text = text.replace("**", "")  # bold markers are formatting, not content
    source_text = sources[source_id].replace("**", "")
    source_lower = source_text.lower()

    for n in NUMBER_RE.findall(text):
        if n not in source_text:
            return ["unsupported_fact"]

    for word in PROPER_NOUN_RE.findall(text):
        if word.lower() not in source_lower:
            return ["unsupported_fact"]

    # A story is long free text; a bullet from it must be one resume sentence, not a copy.
    if source_id.startswith("story_") and (len(text.split()) > STORY_MAX_WORDS or SENTENCE_BREAK_RE.search(text)):
        return ["story_too_long"]

    return []
