# Portable local knowledge retrieval

## Intent

Build persistent RAG over the second prompt's story and uploaded files. The user chose a local prototype using an embedding API and explicitly requires access from different models and agents. Their latest instruction is to plan and implement in this chat. Run natively, without Docker. Preserve the existing first prompt taxonomy and second prompt narrative format.

## Architecture

Flask owns a knowledge service. SQLite stores original documents, exact source spans, chunks, indexing manifests, embedding cache, and an FTS5 keyword index. Qdrant's Python local mode stores dense vectors on disk. A model-independent HTTP search API returns source text and citations, independently of answer generation.

Embeddings use a protocol with `embed_documents(texts)` and `embed_query(text)`. Ship adapters for OpenAI-compatible HTTP APIs, Cohere's native v2 API, and Ollama's native embedding API. Provider, endpoint, model, optional dimensions, revision, and query/document prefixes are configurable. No OpenAI SDK is required. Existing OpenAI credentials may supply the initial provider; they are not required by the interfaces or database. With no configured provider, explicitly report lexical-only operation; never manufacture embeddings.

The embedding profile fingerprints provider, endpoint, model, revision, dimensions, and prefixes, excluding secrets. A profile has its own vector collection. Changing answer models never requires reindexing. Changing the embedding profile requires an explicit rebuild from preserved sources; do not compare incompatible vectors.

## Sources and indexing

- Preserve exact original text, title, document identity, version, source type, and supplied taxonomy metadata.
- Use Unicode character spans so citations can reconstruct exact source excerpts. Start with a maximum of 1,600 characters and 200 characters overlap, respecting headings and whitespace. Character limits are provider-independent and are not advertised as exact token counts.
- Retain PDF page spans and DOCX paragraph text. Reject empty/scanned documents with a clear extraction error; OCR and legacy binary DOC are outside this version.
- Re-uploading the same document/content is idempotent. Stable document IDs support replacement. Different files with the same title remain distinct.
- Batch and cache embeddings by owner, profile, and embedded content hash. Validate vector count, finite numbers, nonzero norm, and dimensions. Retry transient HTTP failures with bounded backoff and timeouts.
- Publish a document only after all its vectors have been written. Failed imports/rebuilds preserve the previous searchable version. Filter dense searches to the active source versions.
- Remove obsolete vectors and unreferenced cached vectors on replacement/deletion. Sources survive restarts and dates; remove automatic daily profile deletion.

## Retrieval and access

- Assign new opaque server-generated avatar IDs in a signed HttpOnly browser session. Do not use caller-supplied filesystem paths or accept another avatar's ID as authorization.
- The search API accepts either the owning browser session or an owner-scoped bearer token minted by that session. Store only token hashes and support revocation. This is local prototype access control, not a hosted account system.
- Default to hybrid dense + SQLite BM25 retrieval when embeddings are configured; otherwise explicitly use lexical retrieval. Support dense/lexical modes for comparison.
- Retrieve up to 20 candidates per method, merge ranks with RRF (constant 60), remove heavily overlapping passages, and return at most 10 results (default 5).
- An optional configurable cosine cutoff starts at 0.30; it is an experimental rejection setting, not a probability or universal relevance guarantee.
- Return document/chunk IDs, version, source spans/page/section, original text, method-specific scores, timings, and warnings. Do not expose provider credentials.
- Missing evidence returns an empty result list, never the first document or a sample person's biography.

## App integration

Story import, custom text, and each uploaded file enter the same service. Preserve legacy JSON imports by converting all original experience/subtopic text to a source document. Continue saving existing profile/story JSON files for compatibility, but use the persistent service for retrieval.

The playground calls the same search service and shows source excerpts. Answer generation is separately configurable (OpenAI-compatible or Ollama HTTP); extractive mode returns source excerpts without pretending an LLM generated an answer. Treat retrieved documents as untrusted evidence, preserve asked/planned/completed distinctions, and require source markers for generated answers. Display extraction/indexing errors and keep the onboarding step open after failure.

## Evaluation

Provide a CLI comparing lexical, dense, and hybrid retrieval on a small checked-in synthetic dataset with answerable/paraphrased/exact-term/multi-source/unanswerable cases. Report Hit@k, Recall@k, Precision@k, nDCG@k, empty-result accuracy on unanswerable questions, and p50/p95 latency. Label expected document IDs and source evidence, not generated answers. Report actual embedding calls/tokens/cache statistics when available; do not invent benchmark improvements or automated faithfulness scores.

## Verification

Use real temporary SQLite and Qdrant stores with deterministic test embeddings, plus HTTP contract tests for all three embedding adapters. Test persistence, exact offsets, Unicode/fences, replacements/deletions, failure rollback, cache reuse, profile migration, mixed dimensions, missing evidence, session/token ownership, malicious filenames/session IDs, and unchanged legacy story behavior. Run a live smoke check on public synthetic text using available API credentials if possible. Never print credentials or upload existing private profile contents during verification.
