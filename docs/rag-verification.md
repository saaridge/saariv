# Portable RAG verification — 2026-10-18

## Automated checks

- 54 Python unittest cases passed, including real temporary SQLite/Qdrant stores, provider wire contracts, restart persistence, profile migration, failed import rollback, deferred cleanup, duplicate/replaced/deleted sources, PDF pages, exact Unicode spans, browser ownership and agent token access.
- 10 Node tests passed, covering story import, signed-session browser requests, direct playground migration status, file preservation, error handling, and safe source rendering.
- JavaScript syntax, Python compilation, dependency compatibility, and Git whitespace checks passed.
- One independent read-only code review identified four lifecycle/browser defects. Each was reproduced with regression tests, fixed, and followed by a green full suite.

## Live embedding benchmark

The supplied credential was saved only in the ignored local environment as `EMBEDDING_API_KEY`. Existing answer-model credentials and settings were preserved. The live provider used the configurable compatible adapter with `text-embedding-3-small`; Cohere and Ollama adapters were verified with HTTP contract tests, not live credentials.

Dataset: `evals/retrieval.json`, five synthetic documents, eight answerable questions, two unanswerable questions, k=3. This is a small functional demonstration, not a production-quality benchmark.

| Retrieval | Evidence found (answerable questions) | Recall@3 | nDCG@3 | Unanswerable empty results | p95 retrieval latency |
|---|---:|---:|---:|---:|---:|
| SQLite keyword | 7/8 | 0.875 | 0.875 | 2/2 | 1.701 ms |
| Dense vectors | 8/8 | 1.000 | 1.000 | 2/2 | 760.174 ms |
| Hybrid | 8/8 | 1.000 | 1.000 | 2/2 | 615.502 ms |

The benchmark reported 21 embedding API calls and 395 input tokens. These counts cover that benchmark run only. The answering API was not called by the evaluator. Latencies include network calls for query embeddings and vary between runs.

Keep a representative, held-out set of real source questions before choosing chunk sizes, score cutoffs or an embedding model. Generated-answer faithfulness is a separate evaluation; valid citation markers alone do not prove every claim.

## Running-app checks

Native Flask served `http://127.0.0.1:8080/try`. The in-app browser successfully imported a synthetic story, displayed a cited source excerpt, rebuilt the saved story from keyword mode into live vectors, displayed semantic + keyword status, and retrieved the career passage for a paraphrased technical-interview question.

An independent HTTP client verified:

- Health and live embedding import: HTTP 200.
- Owner-scoped agent token creation and vector search: HTTP 200.
- Agent-token write attempt: HTTP 403.
- Owner deletion and token revocation: HTTP 200.
- Search with the revoked token: HTTP 401.
- Deleted test avatar: zero source documents and zero vectors remaining.

Synthetic browser/API sources were removed after verification. No existing private profiles were uploaded for these checks. Runtime-only JSON reports and the browser screenshot are in the ignored `data/verification/` folder.

## Follow-up test on the running app

The existing browser avatar was tested without replacing its saved story. A direct inventory question and a paraphrase both ranked the hotel research passage first; expanding a citation displayed the original source wording. After a native Flask restart, the same saved story remained retrievable.

The question "Which telescope did I buy?" initially returned an unrelated source because keyword search matched the question word "which" in "which topics to share." A regression test reproduced the failure in lexical and hybrid search. Adding "which" to the existing question-word filter fixed this case; the running browser now responds that its sources do not contain enough information. This specific fix does not establish perfect relevance for every unsupported question.

Fresh verification after that fix:

- 55 Python tests and 10 JavaScript tests passed. Existing upstream PyPDF2 deprecation and Qdrant SQLite resource warnings remain.
- 41 live HTTP checks passed using an isolated synthetic session: actual embedding import, three stored vectors, duplicate import handling, dense and hybrid paraphrase retrieval, exact citation spans, Markdown file import, duplicate file handling, read-only agent search, denied writes, session isolation, key revocation, and deletion of all temporary sources and vectors.
- Keyword-only search missed the paraphrase while dense and hybrid ranked the expected passage first. This was recorded as a baseline comparison, not hidden as an application success.
- The existing chat-model credential returned HTTP 401 in a separate diagnostic. Generated answers remain unavailable; the playground displays original source excerpts. The supplied embedding credential was used only for embeddings, and no model credential settings were changed.

The follow-up report is `data/verification/local-app-check-2026-10-18.json`; the browser screenshot is `data/verification/local-app-test-2026-10-18.png`. These runtime artifacts are ignored by Git. The application remains running natively at `http://127.0.0.1:8080/try`.
