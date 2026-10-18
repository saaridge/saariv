# Portable RAG Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task in the current chat. Steps use checkbox syntax for tracking.

**Goal:** Persist and search stories/files with interchangeable embedding providers and an agent-accessible search API.

**Architecture:** A focused `knowledge` package wraps configurable HTTP embedding adapters, SQLite source/keyword/cache storage, and Qdrant Local vector storage. Flask onboarding and the playground share the service; agents receive text/citations through a separate authorized search endpoint.

**Tech Stack:** Python >=3.11, Flask, standard-library HTTP/SQLite, qdrant-client, existing PDF/DOCX readers, unittest and node:test.

**Spec:** `docs/superpowers/specs/2026-10-18-portable-rag-design.md`

## Global Constraints

- Run natively, without Docker.
- Preserve the existing first prompt taxonomy and second prompt narrative format.
- No OpenAI SDK is required.
- Changing answer models never requires reindexing.
- Changing the embedding profile requires an explicit rebuild from preserved sources.
- Sources survive restarts and dates; remove automatic daily profile deletion.
- Never print credentials or upload existing private profile contents during verification.

## Review Focus

- Mid-import HTTP/vector failures must leave the old document searchable.
- Another browser or an agent token must never select a different avatar through request parameters.
- Equal vector dimensions from different embedding profiles must not make them interchangeable.
- Unicode, fenced code, and page boundaries must retain exact source spans.
- Empty/scanned uploads, API outages, and source-free questions must not produce fabricated success or sample biographies.

## Execution decisions

The user explicitly requested planning and implementation together; execute after writing/reviewing these artifacts without another permission round. Work on a `codex/portable-rag` branch in the existing checkout, preserving the uncommitted prompt changes and keeping the native app at its known path. Leave changes uncommitted for review. Implement inline; request one independent code review after the whole change.

## Task 1: Provider contracts and source chunking

**Files:** Create `knowledge/config.py`, `knowledge/embeddings.py`, `knowledge/chunking.py`, `knowledge/__init__.py`; tests in `tests/test_knowledge_providers.py` and `tests/test_knowledge_chunking.py`.

**Interfaces:** `Settings.from_env(base_dir)`, `EmbeddingProvider.embed_documents(texts)`, `EmbeddingProvider.embed_query(text)`, `chunk_document(text, title, metadata, size=1600, overlap=200) -> list[dict]` with exact start/end offsets.

- [x] Write failing tests for heading/fence/Unicode spans and long sections; three wire formats, order, error redaction, retries, wrong vector dimensions, distinct query/document roles, profile identity.
- [x] Run these tests; confirm missing functionality fails.
- [x] Implement immutable settings, provider factory, HTTP adapters, vector validation, and chunking.
- [x] Run the task's tests; confirm all pass.

## Task 2: Persistent source/vector service

**Files:** Create `knowledge/store.py`, `knowledge/service.py`; tests in `tests/test_knowledge_service.py`; update `requirements.txt`, `.gitignore`.

**Interfaces:** `KnowledgeService(settings, provider=None)`, `ingest(owner, document_id, text, title, source_type, metadata) -> dict`, `search(owner, query, limit=5, mode='auto') -> dict`, `documents(owner)`, `delete_document(owner, document_id)`, `reindex(owner)`, `status(owner)`, `close()`.

- [x] Write failing tests using deterministic provider fixtures and real temporary SQLite/Qdrant storage for persistence, paraphrase retrieval, cache reuse, owner isolation, replacement, deletion, rollback, profile mismatch and rebuild.
- [x] Run the tests and confirm failures.
- [x] Implement transactional source publication, profile collections, filtered dense search, FTS5 retrieval, RRF, source references, cache metrics and explicit missing-evidence behavior.
- [x] Run all service/provider/chunking tests.

## Task 3: Flask and agent API integration

**Files:** Create `knowledge/web.py`, `knowledge/answers.py`; modify `app.py`, `.env.example`, `static/js/main.js`, `templates/try.html`; tests in `tests/test_knowledge_api.py`, extend existing story/JS tests.

**Interfaces:** `register_knowledge_routes(app, service_factory)`, server-derived avatar ownership; POST `/api/knowledge/search`, GET `/api/knowledge/status`, GET `/api/knowledge/documents`, DELETE `/api/knowledge/documents/<id>`, POST `/api/knowledge/reindex`, POST/DELETE `/api/knowledge/token`.

- [x] Write failing API tests for onboarding-to-search, unknown questions, session spoofing, token access/revocation, safe upload names, PDF pages, indexing errors, persistence, and no automatic cleanup.
- [x] Run the tests and confirm failures.
- [x] Integrate all three onboarding inputs; preserve original text and compatibility exports. Remove daily source deletion and sample/first-result fallbacks.
- [x] Add configurable answer generation, grounded prompt, safe extractive fallback, and source rendering using DOM text nodes.
- [x] Make the frontend adopt server-issued session IDs and show indexing failures/status without advancing after errors.
- [x] Run Python and JavaScript suites.

## Task 4: Evaluation, documentation, and live verification

**Files:** Create `knowledge/evaluate.py`, `evals/retrieval.json`, `docs/rag.md`; update `README.md`; test evaluation metrics in `tests/test_knowledge_evaluation.py`.

**Interfaces:** `python -m knowledge.evaluate --dataset evals/retrieval.json --modes lexical,dense,hybrid --k 5` runs in disposable storage by default and emits JSON metrics.

- [x] Write failing tests for known metric values and unanswerable queries; implement evaluator.
- [x] Document provider configuration examples, bearer-token search, indexing/migration/deletion, corpus persistence, score interpretation, source-grounded evaluation and local-process limits.
- [x] Run all tests, JS syntax check, Python compilation, and diff whitespace checks.
- [x] Request one fresh code review; address concrete defects with regression tests.
- [x] Run an API smoke check on synthetic public text when credentials permit; record actual outcomes without claiming unavailable provider live tests.
- [x] Restart Flask natively, verify onboarding/search/health routes, and deliver the plan, implementation, test results, and any remaining configuration requirement.
