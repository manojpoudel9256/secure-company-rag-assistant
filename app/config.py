"""Central configuration. Everything security-relevant lives here so it is easy to review."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent

# Only this folder is ever ingested into the public index.
PUBLIC_DOCS_DIR = ROOT / "data" / "public"
# Internal docs are read ONLY to collect their `sensitive_terms` for the output guard.
# Their body text is never chunked, indexed or sent to the model.
INTERNAL_DOCS_DIR = ROOT / "data" / "internal"

INDEX_DIR = ROOT / "index"
PUBLIC_INDEX_PATH = INDEX_DIR / "public_index.json"
DENYLIST_PATH = INDEX_DIR / "denylist.json"
AUDIT_LOG_PATH = ROOT / "logs" / "audit.jsonl"

# The public bot may only index documents carrying exactly this label.
ALLOWED_CLASSIFICATION = "public"
KNOWN_CLASSIFICATIONS = {"public", "internal", "confidential"}

# Contact details that are intentionally public. Any other email/phone found in
# a public document is treated as accidental PII and redacted at ingestion.
PII_ALLOWLIST = {
    "info@tsubasa-cloudworks.example",
    "careers@tsubasa-cloudworks.example",
    "03-0000-1234",
}

# Retrieval
TOP_K = 4
MIN_SCORE = 2.5  # below this the bot says it has no information (calibrated by eval)
MIN_COVERAGE = 0.5  # share of the question's key words that the best section must contain

# LLM
MODEL = os.environ.get("RAG_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("RAG_EFFORT", "low")  # short factual answers do well at low effort
MAX_QUESTION_CHARS = 500

# Demo mode shows WHY an answer was blocked (useful for the portfolio demo). In production
# set RAG_DEMO_MODE=0: blocked answers then look exactly like "no information", so the
# API never confirms that a sensitive topic exists.
DEMO_MODE = os.environ.get("RAG_DEMO_MODE", "1") == "1"

# Rate limiting (per client IP, in-memory)
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 60

NO_INFO_MESSAGE = (
    "I don't have public information about that. I can answer questions about "
    "Tsubasa Cloudworks' open roles, salaries for posted roles, hiring process, "
    "benefits, offices and products. For anything else, please contact "
    "careers@tsubasa-cloudworks.example."
)
INJECTION_MESSAGE = (
    "I can't change how I work or reveal internal instructions. I can only answer "
    "questions using Tsubasa Cloudworks' public information."
)
