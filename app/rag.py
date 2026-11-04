"""The RAG pipeline: guard input -> retrieve -> generate -> guard output -> audit log."""
import hashlib
import json
import time
from dataclasses import dataclass, field

from . import config
from .guard import check_input, check_output, load_denylist
from .llm import answer_extractively, answer_with_claude, has_claude_credentials
from .retriever import Retriever


@dataclass
class Answer:
    answer: str
    sources: list[dict] = field(default_factory=list)
    status: str = "answered"  # answered | no_info | blocked_input | blocked_output
    reason: str | None = None
    mode: str = "extractive"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class RagPipeline:
    def __init__(self, mode: str | None = None):
        self.retriever = Retriever.load()
        self.denylist = load_denylist()
        self.mode = mode or ("claude" if has_claude_credentials() else "extractive")

    def ask(self, question: str, client_id: str = "local") -> Answer:
        question = question.strip()
        result = self._ask(question)
        self._audit(question, result, client_id)
        return result

    def _ask(self, question: str) -> Answer:
        if not question:
            return Answer(config.NO_INFO_MESSAGE, status="no_info", mode=self.mode)

        reason = check_input(question, self.denylist)
        if reason == "prompt_injection":
            return Answer(config.INJECTION_MESSAGE, status="blocked_input", reason=reason, mode=self.mode)
        if reason:
            # Same wording as "not found", so the reply does not confirm a secret exists.
            return Answer(config.NO_INFO_MESSAGE, status="blocked_input", reason=reason, mode=self.mode)

        chunks = [c for c in self.retriever.search(question) if c["score"] >= config.MIN_SCORE]
        if not chunks or max(c["coverage"] for c in chunks) < config.MIN_COVERAGE:
            return Answer(config.NO_INFO_MESSAGE, status="no_info", mode=self.mode)

        if self.mode == "claude":
            text = answer_with_claude(question, chunks)
        else:
            text = answer_extractively(question, chunks)
        if text.strip().upper().startswith("NO_ANSWER"):
            return Answer(config.NO_INFO_MESSAGE, status="no_info", mode=self.mode)

        reason = check_output(text, self.denylist)
        if reason:
            return Answer(config.NO_INFO_MESSAGE, status="blocked_output", reason=reason, mode=self.mode)

        sources = [
            {"id": f"S{i}", "title": c["title"], "section": c["section"], "doc_id": c["doc_id"],
             "updated": c["updated"], "score": c["score"]}
            for i, c in enumerate(chunks, 1)
        ]
        cited = [s for s in sources if f"[{s['id']}]" in text] or sources[:1]
        return Answer(text, sources=cited, mode=self.mode)

    def _audit(self, question: str, result: Answer, client_id: str) -> None:
        config.AUDIT_LOG_PATH.parent.mkdir(exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            # Client identity is hashed so the log does not store raw IP addresses.
            "client": hashlib.sha256(client_id.encode()).hexdigest()[:12],
            "question": question[:300],
            "status": result.status,
            "reason": result.reason,
            "sources": [s["doc_id"] + ":" + s["section"] for s in result.sources],
            "mode": result.mode,
        }
        with config.AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
