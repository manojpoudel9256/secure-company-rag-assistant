"""PII detection and redaction used at ingestion time and again on every answer."""
import re

from .config import PII_ALLOWLIST

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Japanese phone formats such as 03-1234-5678, 090-1234-5678, +81-90-1234-5678
PHONE_RE = re.compile(r"(?:\+81[- ]?)?\b0\d{1,3}-\d{2,4}-\d{3,4}\b")
# My Number (12 digits) / credit-card-like long digit runs
LONG_ID_RE = re.compile(r"\b\d{12,16}\b")


def find_pii(text: str) -> list[str]:
    hits = []
    for pattern in (EMAIL_RE, PHONE_RE, LONG_ID_RE):
        for match in pattern.findall(text):
            if match not in PII_ALLOWLIST:
                hits.append(match)
    return hits


def redact_pii(text: str) -> tuple[str, list[str]]:
    found = find_pii(text)
    for item in found:
        text = text.replace(item, "[REDACTED]")
    return text, found
