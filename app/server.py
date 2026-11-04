"""FastAPI server for the public company assistant.

Run:  uvicorn app.server:app --port 8000
"""
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import config
from .rag import RagPipeline

app = FastAPI(title="Tsubasa Cloudworks Public Assistant", docs_url=None, redoc_url=None)
pipeline = RagPipeline()
_requests: dict[str, deque] = defaultdict(deque)

STATIC = config.ROOT / "app" / "static"


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=config.MAX_QUESTION_CHARS)


def rate_limited(client: str) -> bool:
    now = time.monotonic()
    window = _requests[client]
    while window and now - window[0] > config.RATE_LIMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= config.RATE_LIMIT_REQUESTS:
        return True
    window.append(now)
    return False


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info():
    return {"mode": pipeline.mode, "model": config.MODEL if pipeline.mode == "claude" else None,
            "documents": len({c["doc_id"] for c in pipeline.retriever.chunks})}


@app.post("/api/ask")
def ask(body: Question, request: Request):
    client = request.client.host if request.client else "unknown"
    if rate_limited(client):
        raise HTTPException(429, "Too many questions. Please wait a minute and try again.")
    try:
        result = pipeline.ask(body.question, client_id=client).to_dict()
    except Exception:
        # Never return stack traces or internal details to the public.
        raise HTTPException(500, "Something went wrong. Please try again later.")
    if not config.DEMO_MODE:
        result.pop("reason", None)
        result.pop("mode", None)
        if result["status"] in ("blocked_input", "blocked_output") and result["answer"] == config.NO_INFO_MESSAGE:
            result["status"] = "no_info"
    return result
