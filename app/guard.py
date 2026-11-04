"""Input and output guards.

These are a second line of defense. The first line is that confidential text is never
indexed, so the model cannot leak what it never receives.
"""
import json
import re

from . import config
from .pii import find_pii

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (the |your |all )?(instructions|rules|system)",
    r"(reveal|show|print|repeat|output|leak) (me )?(your|the) (system|hidden|initial|internal) (prompt|instructions|rules)",
    r"\bsystem prompt\b",
    r"\b(developer|god|admin|debug|jailbreak|dan) mode\b",
    r"you are now\b",
    r"pretend (to be|you are)",
    r"act as (an? )?(admin|administrator|hr manager|developer|root)",
    r"</?(system|source|instructions)>",
    r"base64|rot13",
]

# Requests for categories of information that are never public, even if phrased politely.
SENSITIVE_REQUEST_PATTERNS = [
    # Note: we deliberately do NOT try to detect "salary of <person name>" with regex - it
    # cannot tell names from role titles. Individual salaries are simply never indexed,
    # and known names are covered by the denylist.
    r"\b(every|each|all|individual|specific) (employee|staff|person)('s)?\b.{0,30}\b(salar\w*|pay|earn\w*)\b",
    r"\b(employee|staff)('s)? (personal|private|home|phone|email|address|salar\w*|list|names)\b",
    r"\b(personal|private) (data|information|details)\b",
    r"\b(confidential|internal[- ]only|leaked?|secret)\b",
    r"\b(unreleased|upcoming|future|secret) (product|project|plans?)\b",
    r"\b(roadmap|acquisition|merger|layoffs?|funding round|valuation)\b",
    r"\b(rejected|failed) candidates?\b|\bcandidate (scores?|results?|names?)\b",
    r"\b(password|api key|credentials?|token)\b",
]


def load_denylist() -> list[str]:
    if config.DENYLIST_PATH.exists():
        return json.loads(config.DENYLIST_PATH.read_text(encoding="utf-8"))
    return []


def check_input(question: str, denylist: list[str]) -> str | None:
    """Return a block reason, or None when the question may proceed."""
    if len(question) > config.MAX_QUESTION_CHARS:
        return "too_long"
    lowered = question.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            return "prompt_injection"
    for pattern in SENSITIVE_REQUEST_PATTERNS:
        if re.search(pattern, lowered):
            return "sensitive_request"
    if any(term.lower() in lowered for term in denylist):
        return "sensitive_request"
    return None


def check_output(answer: str, denylist: list[str]) -> str | None:
    """Return a block reason if the answer contains anything that must not leave the system."""
    lowered = answer.lower()
    for term in denylist:
        if term.lower() in lowered:
            return "sensitive_term_in_answer"
    if find_pii(answer):
        return "pii_in_answer"
    return None
