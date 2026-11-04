# Secure Company Assistant (RAG demo)

A public Q&A assistant for a company website. Students and job seekers can ask about **open roles,
starting salaries, hiring process, number of employees, benefits and facilities**. The assistant
answers **only from approved public documents**, cites its sources, says "I don't know" when it
doesn't know, and is built so that **internal documents cannot leak**.

> The company, *Tsubasa Cloudworks K.K.*, and all of its data are fictional.

## Why this project

Generic chatbots answer questions about a company from whatever is on the internet, which may be
outdated or wrong. Companies want an assistant that uses *their* real data. They also have internal
documents (salaries, roadmaps, candidate notes) that must never be exposed. This demo shows how to
build both properties into the architecture.

## Results

`python -m eval.run_eval` (offline mode):

| Check | Result |
|---|---|
| Accuracy (correct fact **and** correct source cited) | 24 / 24 |
| Says "I don't know" for off-topic questions | 4 / 4 |
| Attack prompts with zero leaked data | 17 / 17 |
| Public index free of sensitive terms and canaries | yes |
| Confidential file placed in the public folder is rejected | yes |

The retriever was tuned on this same question set, so treat accuracy as a regression check, not a
benchmark. Add new questions to `eval/cases.json` to measure generalisation.

## Architecture

```
            data/public/*.md                       data/internal/*.md
                  |                                        |
     [Ingestion guard]                          only `sensitive_terms` read
     - label must be "public"                              |
     - PII redaction                                       v
     - no sensitive term allowed  ---------------->  denylist.json
                  |                                        |
                  v                                        |
          public_index.json                                |
                  |                                        |
 question -> [Input guard] -> [BM25 retrieval] -> [Claude, grounded] -> [Output guard] -> answer + sources
             injection,        relevance and       sources only,         denylist terms,
             sensitive         coverage            cite [S1],            canaries, PII
             topics            thresholds          NO_ANSWER rule
                                                                            |
                                                                    audit log (hashed client id)
```

## Security design

The core rule: **the model can't leak what it never receives.**

1. **Separate data at the source.** Only `data/public` is indexed. Internal documents are never chunked,
   embedded or sent to the model.
2. **Mandatory labels.** Every public document must declare `classification: public`. A missing or wrong
   label stops ingestion, so a confidential file copied into the wrong folder is caught.
3. **PII redaction at ingestion.** Emails and phone numbers that are not on the public allowlist are redacted.
4. **Canary strings.** Each internal document carries a unique marker (for example `CANARY-SAL-7F3A`). The eval
   checks that no canary ever appears in the index or in any answer.
5. **Input guard.** Blocks prompt-injection patterns and requests for clearly confidential topics.
6. **Uniform refusals.** A blocked sensitive question gets the same reply as an unknown topic, so the
   assistant never confirms that a secret exists. The UI's "blocked by guard" tag is shown only in
   demo mode; set `RAG_DEMO_MODE=0` in production so the API response is identical too.
7. **Grounded generation.** The system prompt lets Claude use only the provided sources, requires citations,
   treats source text as data and not instructions, and returns `NO_ANSWER` when the answer isn't there.
8. **Output guard.** Every answer is checked against the denylist (names, codenames, figures from internal
   docs) and PII patterns before it is returned.
9. **Operational controls.** Rate limiting per client, no stack traces returned to users, security headers
   (CSP, nosniff, no-referrer), an XSS-safe UI that renders text only, and an audit log with hashed client ids.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m app.ingest              # build the public index
python -m eval.run_eval           # accuracy + security checks
uvicorn app.server:app --port 8000
```

Open http://localhost:8000.

### Modes

- **Offline (default without a key):** extractive answers that quote the best-matching lines. No API cost.
- **Claude:** set `ANTHROPIC_API_KEY` to get natural, grounded answers from `claude-opus-5-5` at low effort.
  Override with `RAG_MODEL` and `RAG_EFFORT`. Server-side refusal fallback is enabled
  (`fallbacks: "default"`).

## Project layout

```
app/
  config.py      security settings, thresholds, allowlists
  ingest.py      ingestion guard, chunking, denylist build
  pii.py         PII detection and redaction
  retriever.py   BM25 + heading boost + query coverage
  guard.py       input and output guards
  llm.py         Claude grounded generation + offline extractive mode
  rag.py         pipeline and audit log
  server.py      FastAPI, rate limit, security headers
  static/        chat UI
data/public/     documents the assistant may use
data/internal/   confidential documents (never indexed; used to test for leaks)
eval/            test questions and the evaluation script
```

## Next steps

- Hybrid retrieval (BM25 plus embeddings) and Japanese-language questions
- Role-based access (a logged-in employee bot reading from a separate internal index)
- An LLM-as-judge eval for answer quality in Claude mode
- Document freshness warnings when a source's `updated` date is old
