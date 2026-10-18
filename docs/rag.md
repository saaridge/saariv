# Portable local RAG

Saariv indexes the second prompt's narrative and each uploaded file into persistent local knowledge. Any connected agent can search that knowledge and use the returned text with its own answering model.

## Run natively

Use Python 3.11 or newer. In the current development checkout, dependencies are installed in `.venv-rag`:

```sh
.venv-rag/bin/python -m flask --app app run --host=127.0.0.1 --port=8080
```

For a new installation, create a virtual environment with your Python >=3.11 interpreter, install `requirements.txt`, and copy `.env.example` to `.env`. Select an embedding provider below. The sample environment explicitly selects keyword-only search until you configure one.

Qdrant runs inside the Python process and saves vectors to disk. No Docker or separate database server is needed. Use one application process, with one shared service/client. Do not enable Flask's reloader or start another process against the same vector directory. The existing Gunicorn entrypoint uses one worker; all knowledge operations are serialized with a lock. Local mode is for this prototype, not a multi-worker hosted deployment.

## Choose an embedding provider

All providers implement `embed_documents(texts)` and `embed_query(text)`. The app uses no OpenAI SDK. Compatible HTTP transport can target any service implementing that API; Cohere and Ollama have separate native adapters.

### Any OpenAI-compatible embedding API

```dotenv
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=https://your-provider.example/v1
EMBEDDING_MODEL=your-embedding-model
EMBEDDING_API_KEY=your-provider-key
```

The adapter posts to `EMBEDDING_BASE_URL/embeddings`. Leave `EMBEDDING_DIMENSIONS` empty unless the chosen model supports a requested output size. Providers requiring query/document instructions can use `EMBEDDING_QUERY_PREFIX` and `EMBEDDING_DOCUMENT_PREFIX`.

### Cohere native API

```dotenv
EMBEDDING_PROVIDER=cohere
EMBEDDING_BASE_URL=https://api.cohere.com
EMBEDDING_MODEL=embed-v4.0
EMBEDDING_API_KEY=your-cohere-key
```

The adapter calls `/v2/embed` with `search_document` for passages and `search_query` for questions. It requests float embeddings and rejects truncation.

### Ollama native API

If an Ollama instance and embedding model are already available:

```dotenv
EMBEDDING_PROVIDER=ollama
EMBEDDING_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL=embeddinggemma
EMBEDDING_API_KEY=
```

The adapter calls `/api/embed`. Running/installing Ollama is optional; the hosted embedding API adapters do not need it.

### Keyword-only operation

```dotenv
EMBEDDING_PROVIDER=none
```

The API and playground explicitly report lexical search. Dense/hybrid requests fail clearly instead of producing fake embeddings. In a legacy installation with only `OPENAI_API_KEY` and no explicit provider variables, that key supplies the initial compatible embedding and chat adapters. Set provider variables to choose a different service or disable that behavior.

## Answer models are independent

The search API returns ordinary text and source locations. External agents can use those results with any answering model, including models with no embedding endpoint.

The built-in playground supports:

```dotenv
CHAT_PROVIDER=extractive
```

This shows original cited excerpts without calling a generation API. For a compatible chat endpoint, set `CHAT_PROVIDER=openai_compatible`, `CHAT_BASE_URL`, `CHAT_MODEL`, and `CHAT_API_KEY`. For Ollama, set `CHAT_PROVIDER=ollama`, `CHAT_BASE_URL=http://127.0.0.1:11434`, and an installed chat model in `CHAT_MODEL`.

The generation prompt preserves asked/planned/completed distinctions and requests citations. Missing or invalid citation markers, or generation failures, produce an explicitly labeled excerpt fallback. Valid markers establish that a source exists; they do not automatically prove every generated claim. Review answer faithfulness separately.

## Data lifecycle

- SQLite under `KNOWLEDGE_DIR` (default `data/knowledge`) stores source text, Unicode character offsets, metadata, chunks, profile manifests, access-token hashes and cached vectors.
- Qdrant stores dense vectors and source references under the same directory's `vectors/` folder. Sources and vectors survive restarts and dates.
- `tmp_profiles/` contains compatibility exports and existing profile data. Automatic daily deletion has been removed. Back up the local data and stable `data/session.secret` if you need to preserve access across restarts.
- Narrative headings produce sections. Long sections use 1,600-character windows with 200-character overlap by default. These are provider-independent character budgets, not exact token counts. Respect the input limits of the provider/model you select.
- Each uploaded file retains its own identity. PDF citations include page spans. Text PDFs, DOCX, TXT, Markdown, JSON and CSV are supported. Scanned PDFs require OCR before upload; convert binary `.doc` to `.docx`.
- Reimporting `story` replaces that source. Custom text is identified by topic tag. Files use basename plus content identity: identical reuploads deduplicate, and different files with the same name remain separate sources. For an intentional replacement, send exactly one file to the upload endpoint with the owned `replace_document_id` from the document listing.
- Embeddings are cached per owner, provider profile, and embedded content hash. Identical passages reuse cached vectors. Imports are published only after all staged vectors are written.
- Post-publication cleanup failures are reported as recoverable maintenance warnings. Committed sources stay available and compatibility exports are refreshed; rebuild the index to retry cleanup. Pre-publication failures retain the previous committed source.
- Deletion removes active source rows, keyword entries, obsolete vectors, unreferenced cached embeddings, and matching compatibility exports. This is logical deletion, not a forensic disk erasure feature.

Existing profile folders from before this feature are preserved. Reimport their saved `experiences.md` or legacy JSON in the owning browser to populate the new index; the app does not grant access based on an old caller-supplied session identifier.

## Connect another agent

1. Import your story in `/try` and open the playground.
2. Expand **Connect an agent**, create an access key, and copy it.
3. Give that key to your local agent as a secret. It authorizes read access to this avatar only, expires after 30 days, and can be revoked from the same panel.

Example request (replace the token placeholder through your agent's secret configuration):

```http
POST /api/knowledge/search HTTP/1.1
Host: 127.0.0.1:8080
Authorization: Bearer <avatar-access-key>
Content-Type: application/json

{"query":"What did I ask about finding housing?","limit":5,"mode":"auto"}
```

The response contains `results`, `mode`, `embedding_profile_id`, `timings_ms`, and `warnings`. Each result contains `text`, `chunk_id`, `citation_id`, `document_id`, `document_version`, `source` (title, section, filename, character offsets and optional pages), `score`, and `scores`.

The backend derives ownership from the session/token. Other agents do not supply an avatar ID as authorization. Keys are read-only; importing, deleting, rebuilding and minting/revoking keys require the owning browser. There is no cross-origin browser API access. This is local prototype identity, not a hosted account/login system. If the browser cookie is lost, an old session ID is insufficient to recover access; reimport saved sources into a new avatar.

### Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/knowledge/search` | Search with `query`, optional `limit` (1–10), and `mode` (`auto`, `lexical`, `dense`, `hybrid`) |
| GET | `/api/knowledge/status` | Source/vector counts, provider profile, rebuild requirement and usage counters |
| GET | `/api/knowledge/documents` | List the current avatar's saved documents |
| DELETE | `/api/knowledge/documents/<document_id>` | Delete an owned source and its derived index entries |
| POST | `/api/knowledge/reindex` | Rebuild from preserved source text using the current embedding configuration |
| POST | `/api/knowledge/token` | Mint an owner-scoped read token (returned once) |
| DELETE | `/api/knowledge/token` | Revoke this avatar's agent tokens |

## Switch models safely

Changing the answering model leaves the index usable. Embedding profiles fingerprint the provider, endpoint, model, requested dimensions, revision, and query/document prefixes. Credentials are excluded. Use `EMBEDDING_REVISION` to identify intentional weight revisions when an endpoint/model alias stays the same.

After changing embedding configuration, restart the single app process. Vector search/import returns HTTP 409 if documents need rebuilding. In the playground click **Rebuild search index**, or call the reindex endpoint using the owning browser session. Keyword search remains available during a profile mismatch. Failed rebuilds retain the previous source/index manifest; restoring the old provider configuration restores its index after an unsuccessful rebuild. Successful rebuilds prune obsolete vectors.

Matching vector dimensions alone does not imply compatibility. The search service always uses its configured query encoder for the corresponding index; answering agents never need to understand or generate those vectors.

## Evaluate and optimize

```sh
.venv-rag/bin/python -m knowledge.evaluate --dataset evals/retrieval.json --modes lexical,dense,hybrid --k 5 --output /tmp/saariv-evaluation.json
```

The evaluator uses temporary storage, so it can run while Flask owns the main local index. Only the synthetic evaluation corpus is sent to the configured API. With embeddings disabled, it reports dense/hybrid modes as skipped.

The seed dataset has five documents and ten queries, including paraphrases, exact terms, multi-source questions and missing answers. Expand it to 50–100 human-labeled questions from representative sources before making quality claims. Keep a separate held-out set for final comparisons.

Reports include document-level Hit@k, Recall@k, Precision@k (denominator k), binary nDCG@k, expected evidence-string coverage, unanswerable empty-result accuracy, p50/p95 latency, and reported embedding usage. Duplicate documents are removed before document-level metrics. Answerable metrics exclude questions with no relevant documents; absent categories report null. These retrieval reports do not measure generated-answer correctness or faithfulness.

Hybrid search merges 20 dense and 20 keyword candidates with reciprocal rank fusion (constant 60), then removes overlapping passages. Final `score` is a rank-fusion score; method-specific `scores.dense` is cosine similarity and `scores.lexical` is SQLite BM25 (lower is better). None is a probability of truth. `EMBEDDING_MIN_SCORE=0.30` is an experimental cosine cutoff; calibrate it on representative relevant/irrelevant questions after each model change.

Compare retrieval modes first, then vary chunk size/overlap and result count one at a time. Rebuild after changing chunk settings to apply them to saved sources. Record quality, missing-answer behavior, latency, context size, embedding calls and answer-generation tokens together. Usage counters are process-local; input-token counts are unknown when a provider does not report them. Actual cost depends on the provider and answering model prices. Reranking, ANN tuning and a hosted database are later choices driven by measured needs.

## Verification

```sh
.venv-rag/bin/python -m unittest discover -s tests -v
node --test tests/test_story_import.mjs
node --check static/js/main.js
```

Tests use real temporary SQLite/Qdrant databases and deterministic test-only vectors. HTTP contract tests cover all three embedding wire formats; they do not claim live credentials for all providers. Provider failures, invalid vectors, cache reuse, persistence, rebuilds, deletion, Unicode/fenced snippets, PDF pages, authorization, citations and frontend save failures are covered.
