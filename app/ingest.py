"""Build the public search index.

Security rules enforced here (the most important layer):
  1. Only files in data/public are indexed.
  2. Every file must declare `classification: public`. Missing or wrong labels are a hard
     failure, so a confidential file copied into the wrong folder never gets indexed.
  3. Accidental PII in public docs is redacted before indexing.
  4. Internal docs are read only for their `sensitive_terms`, which feed the output guard.
     Their content never enters the index or the model prompt.

Run:  python -m app.ingest
"""
import json
import sys
from pathlib import Path

from . import config
from .pii import redact_pii
from .text import parse_front_matter, tokenize


class IngestionError(Exception):
    pass


def chunk_markdown(doc_id: str, title: str, body: str) -> list[dict]:
    """One chunk per `##` section, so each chunk is a self-contained topic."""
    chunks, heading, lines = [], None, []

    def flush():
        text = "\n".join(l for l in lines if l.strip()).strip()
        if heading and text:
            chunks.append(
                {
                    "id": f"{doc_id}#{len(chunks) + 1}",
                    "doc_id": doc_id,
                    "title": title,
                    "section": heading,
                    "text": text,
                }
            )

    for line in body.splitlines():
        if line.startswith("## "):
            flush()
            heading, lines = line[3:].strip(), []
        elif line.startswith("# "):
            continue
        else:
            lines.append(line)
    flush()
    return chunks


def load_public_chunks(public_dir: Path = config.PUBLIC_DOCS_DIR) -> tuple[list[dict], list[str]]:
    chunks, warnings = [], []
    for path in sorted(public_dir.glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        label = meta.get("classification", "").lower()
        if label != config.ALLOWED_CLASSIFICATION:
            raise IngestionError(
                f"{path.name}: classification is '{label or 'MISSING'}', expected "
                f"'{config.ALLOWED_CLASSIFICATION}'. Refusing to index it into the public bot."
            )
        if meta.get("sensitive_terms"):
            raise IngestionError(f"{path.name}: public documents must not declare sensitive_terms.")
        body, pii = redact_pii(body)
        if pii:
            warnings.append(f"{path.name}: redacted {len(pii)} PII value(s) before indexing")
        title = meta.get("title", path.stem)
        for chunk in chunk_markdown(path.stem, title, body):
            chunk["updated"] = meta.get("updated", "")
            chunk["tokens"] = tokenize(f"{chunk['section']} {chunk['section']} {chunk['text']}")
            chunks.append(chunk)
    return chunks, warnings


def load_denylist(internal_dir: Path = config.INTERNAL_DOCS_DIR) -> list[str]:
    terms = set()
    for path in sorted(internal_dir.glob("*.md")):
        meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        label = meta.get("classification", "").lower()
        if label not in config.KNOWN_CLASSIFICATIONS - {"public"}:
            raise IngestionError(f"{path.name}: internal docs must be labelled internal or confidential.")
        terms.update(meta.get("sensitive_terms", []))
    return sorted(terms)


def build() -> dict:
    chunks, warnings = load_public_chunks()
    denylist = load_denylist()

    # Defense in depth: no public chunk may contain a term that is marked sensitive.
    for chunk in chunks:
        lowered = chunk["text"].lower()
        for term in denylist:
            if term.lower() in lowered:
                raise IngestionError(f"{chunk['id']}: contains sensitive term '{term}'")

    config.INDEX_DIR.mkdir(exist_ok=True)
    config.PUBLIC_INDEX_PATH.write_text(json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    config.DENYLIST_PATH.write_text(json.dumps(denylist, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"chunks": len(chunks), "documents": len({c["doc_id"] for c in chunks}),
            "denylist_terms": len(denylist), "warnings": warnings}


if __name__ == "__main__":
    try:
        stats = build()
    except IngestionError as exc:
        print(f"INGESTION BLOCKED: {exc}")
        sys.exit(1)
    for w in stats.pop("warnings"):
        print(f"WARNING: {w}")
    print(f"Indexed {stats['chunks']} chunks from {stats['documents']} public documents; "
          f"{stats['denylist_terms']} sensitive terms loaded into the output guard.")
