"""Small text utilities: front matter parsing, tokenizing, query expansion."""
import re

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "at", "by",
    "is", "are", "was", "were", "be", "been", "do", "does", "did", "can", "could",
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "this", "that", "these",
    "what", "which", "who", "whom", "how", "when", "where", "why", "there", "their",
    "about", "any", "some", "as", "from", "into", "if", "so", "than", "then", "will",
    "would", "should", "please", "tell", "know", "want", "like", "much", "many",
    "company", "tsubasa", "cloudworks", "have", "has", "get", "give", "now", "currently",
}

# Synonym groups help a keyword retriever understand how candidates actually ask.
SYNONYM_GROUPS = [
    {"salary", "salaries", "pay", "compensation", "wage", "income", "earn"},
    {"benefit", "benefits", "facility", "facilities", "perk", "perks", "welfare", "allowance"},
    {"employee", "employees", "staff", "headcount", "people", "workforce", "size"},
    {"hiring", "hire", "recruit", "recruiting", "recruitment", "selection"},
    {"process", "steps", "stage", "stages", "procedure"},
    {"timeline", "long", "duration"},
    {"role", "roles", "position", "positions", "job", "jobs", "opening", "openings", "vacancy", "vacancies"},
    {"junior", "graduate", "fresher", "entry", "starting"},
    {"holiday", "holidays", "leave", "vacation", "off"},
    {"office", "offices", "location", "located", "headquarters"},
    {"remote", "remotely", "hybrid", "home", "wfh"},
    {"visa", "international", "foreign", "overseas"},
    {"product", "products", "service", "services"},
]


def stem(word: str) -> str:
    """Very light stemmer so 'roles'/'role' and 'interviews'/'interview' match."""
    for suffix in ("ies", "es", "s"):
        if len(word) > 4 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


_SYNONYMS: dict[str, set[str]] = {}
for group in SYNONYM_GROUPS:
    stems = {stem(w) for w in group}
    for s in stems:
        _SYNONYMS.setdefault(s, set()).update(stems)


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


def expand_query(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    for t in tokens:
        for syn in _SYNONYMS.get(t, ()):
            if syn not in expanded:
                expanded.append(syn)
    return expanded


def parse_front_matter(raw: str) -> tuple[dict, str]:
    """Parse a minimal `---` YAML-like header. Lists are semicolon separated."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    header, body = raw[3:end], raw[end + 4 :]
    meta = {}
    for line in header.strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    if "sensitive_terms" in meta:
        meta["sensitive_terms"] = [t.strip() for t in meta["sensitive_terms"].split(";") if t.strip()]
    return meta, body.lstrip("\n")
