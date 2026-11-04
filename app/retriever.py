"""BM25 keyword retrieval over the public index (pure Python, no external services).

BM25 is easy to explain and inspect, which suits a security-focused demo. It can be
swapped for embeddings or hybrid search later without touching the guards.
"""
import json
import math
from collections import Counter

from . import config
from .text import expand_query, tokenize


class Retriever:
    def __init__(self, chunks: list[dict], k1: float = 1.4, b: float = 0.7):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.tf = [Counter(c["tokens"]) for c in chunks]
        # Headings say what a section is about; matching them is a strong relevance signal.
        self.heading = [set(tokenize(f"{c['title']} {c['section']}")) for c in chunks]
        self.section_heading = [set(tokenize(c["section"])) for c in chunks]
        self.lengths = [len(c["tokens"]) for c in chunks]
        self.avg_len = sum(self.lengths) / max(len(chunks), 1)
        df = Counter(t for tf in self.tf for t in tf)
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    @classmethod
    def load(cls) -> "Retriever":
        if not config.PUBLIC_INDEX_PATH.exists():
            raise FileNotFoundError("Index not found. Run: python -m app.ingest")
        return cls(json.loads(config.PUBLIC_INDEX_PATH.read_text(encoding="utf-8")))

    def _coverage(self, original: list[str], i: int) -> float:
        """IDF-weighted share of the question's words (or their synonyms) found in chunk i.

        Words the corpus has never seen ("weather") get the highest weight, so a question
        that only shares a generic word with our docs ("Tokyo") is not treated as answerable.
        """
        if not original:
            return 0.0
        max_idf = max(self.idf.values(), default=1.0)
        total = matched = 0.0
        for t in dict.fromkeys(original):
            w = self.idf.get(t, max_idf)
            total += w
            if t in self.tf[i] or any(s in self.tf[i] for s in expand_query([t])):
                matched += w
        return matched / total

    def search(self, query: str, top_k: int = config.TOP_K) -> list[dict]:
        original = tokenize(query)
        terms = expand_query(original)
        results = []
        for i, chunk in enumerate(self.chunks):
            score = 0.0
            for t in terms:
                f = self.tf[i].get(t)
                if not f:
                    continue
                weight = 1.0 if t in original else 0.5  # synonyms count, but less
                norm = f + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_len)
                score += weight * self.idf.get(t, 0) * f * (self.k1 + 1) / norm
            if score > 0:
                for t in terms:
                    weight = 1.0 if t in original else 0.5
                    if t in self.section_heading[i]:
                        score += 1.5 * weight * self.idf.get(t, 0)
                    elif t in self.heading[i]:
                        score += 0.5 * weight * self.idf.get(t, 0)
                if chunk["id"].endswith("#1"):
                    score += 0.5  # tie-break: a document's first section is usually its overview
                results.append({**chunk, "score": round(score, 3),
                                "coverage": round(self._coverage(original, i), 3)})
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]
