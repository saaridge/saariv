# Marketplace Publishing and Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this subsystem task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create private author drafts and an isolated, approved experience index, then connect homepage query/dictation to safe result cards.

**Architecture:** SQL owns revisions/visibility. A PostgreSQL outbox updates a separate published Qdrant collection. GPT assists query interpretation using the existing chat configuration; retrieval returns safe DTOs.

**Tech Stack:** Flask/Jinja, PostgreSQL text search, existing embedding adapters, Qdrant, vanilla JavaScript, unittest and node:test.

**Spec:** [Marketplace design](../specs/2026-10-21-experience-marketplace-design.md)

**Roadmap:** [Master plan](2026-10-21-experience-marketplace.md)

**Prerequisite:** Foundation/accounts complete. Paid access is completed in Phase 3; funded approval/voting in Phase 5. Keep the live marketplace feature flag off until those gates pass.

## Global Constraints

- Private RAG is not the public search corpus.
- No approved publication from client-side status fields or a guessed owner ID.
- Guest limit four is enforced on the server; real concealed identity is absent from payloads.
- Embedding settings are independent of the current chat model.
- Use test-only approved fixtures until the Phase 5 approval service exists.

## Review Focus

Prevent private draft/full-body/name leaks. Do not publish half-built vector generations, mix embedding spaces, or let stale index hits bypass SQL visibility. Ratings sort a relevant set.

## Task 2.1: Experience and revision domain

**Files:** Create `marketplace/experiences/models.py`, `service.py`, `imports.py`, `routes.py`; migration `002_experiences_search_outbox.py`; `tests/test_marketplace_experiences.py`.

**Interfaces:** `ExperienceService.submit(author_id, draft_id)`; author-owned draft editing with optimistic revision version; immutable submitted/approved revisions and source provenance.

**Test anchor:** `test_submit_is_private_and_creates_no_reward` asserts status `submitted`, no public search hit, and no ledger transaction; `test_other_author_cannot_patch_draft` expects HTTP 403 and unchanged text.

- [ ] Write failing tests for draft ownership, other-user denial, guessed IDs, positive integer price validation, revision conflicts, and attempts to set approved status directly.
- [ ] Run `python -m unittest discover -s tests -p 'test_marketplace_experiences.py' -v`; confirm failures.
- [ ] Implement experience/revision schema, canonical content hashes, exact story/provenance storage, title/teaser/taxonomy, price, and current approved revision pointer.
- [ ] Implement create/edit/submit/archive operations with ownership checks and audit events. Submission alone neither publishes nor grants coins.
- [ ] Bridge the existing story/import flow through verified account ownership. Import produces a private draft; preserve original private documents.
- [ ] Verify new revisions do not replace a live revision before approval, and edits do not create another reward-eligible identity.
- [ ] Run the experience tests and existing narrative/import tests.

## Task 2.2: Outbox and published index

**Files:** Create `marketplace/search/index.py`, `worker.py`; extend publication jobs schema; `tests/test_marketplace_index.py`. Extend existing Qdrant configuration only as necessary for remote mode.

**Interfaces:** `PublishedIndex.index_revision(revision_id, generation)`, `remove_experience(experience_id)`; native worker `python -m marketplace.search.worker`.

**Test anchor:** `test_archived_revision_is_rejected_even_if_vector_remains` returns no card; `test_failed_generation_keeps_previous_generation_active` asserts the active generation and old searchable hit are unchanged.

- [ ] Write failing tests for private source exclusion, revision mismatch, stale archived hits, retry after embedding failure, mixed model profiles, and failed generation rebuild.
- [ ] Run the index tests and confirm failures.
- [ ] Implement idempotent outbox jobs keyed by revision/profile/generation, with bounded retries, lease expiry/recovery, and admin-visible errors.
- [ ] Add PostgreSQL lexical index over approved body text and separate Qdrant collection with exact revision/chunk source references.
- [ ] Reuse embedding adapters and profile identity. Build new generations before switching, keeping the old usable index on failure.
- [ ] Support Qdrant server URL for shared web/worker processes. Ensure private/local test paths and published collections cannot collide.
- [ ] Re-read SQL status/current revision before returning each candidate. A stale vector hit cannot expose an archived revision.
- [ ] Run index tests with deterministic embeddings and a disposable index; verify native worker crash/retry behavior. No real source contents leave the machine during deterministic tests.

## Task 2.3: Query assistance, relevant candidates, and safe cards

**Files:** Create `marketplace/search/service.py`, `routes.py`; `tests/test_marketplace_search.py`.

**Interface:** `SearchService.search(principal, query, cursor=None) -> SearchPage`.

**Test anchor:** `test_guest_request_cannot_bypass_four_card_limit` seeds six relevant experiences and asserts exactly four items, `next_cursor is None`, every `author is None`, and zero raw story fields.

- [ ] Write failing tests for semantic paraphrases, lexical fallback, empty/unanswerable queries, unrelated popular authors, chunk deduplication, guest cap bypass, body/author-field leakage, and stable paging.
- [ ] Run search tests and confirm failures.
- [ ] Implement bounded query normalization through the existing chat adapter, with validated structured intent/taxonomy and original-query fallback. Never send paid/private bodies into this preprocessing prompt.
- [ ] Retrieve dense and lexical candidates, combine with reciprocal rank fusion, deduplicate to experiences, and apply the relevance cutoff.
- [ ] Apply author rating order after relevance filtering; until Phase 5 all synthetic authors use the neutral contract score. Use stable query snapshots/cursors and IDs for tie breaks.
- [ ] Create allowlisted card serialization. Strip guest name/avatar/author ID/links and all raw body/source data from guest and locked results.
- [ ] Enforce cap four/no next cursor for guests and 12 per signed in page. Rate-limit query/GPT/embedding work.
- [ ] Run search tests and inspect raw JSON/HTML for prohibited fields, including error paths and stale index cases.

## Task 2.4: Homepage, dictation, and author editor

**Files:** Create `templates/marketplace/home.html`, `editor.html`, `experience.html`; `static/js/marketplace.js`, `authoring.js`; `tests/test_marketplace_ui.mjs`. Modify homepage route in `app.py`; reuse `static/js/story-dictation.js` and shared styles.

**Test anchor:** `test_dictated_query_remains_editable_and_submits_once` injects recognition text, changes it manually, submits, and asserts one search request with the final edited query; `test_guest_card_creates_resume_intent` asserts the selected experience is preserved through login.

- [ ] Write failing controller tests for typed/dictated query submission, unsupported recognition, denied microphone, stop/cancel, guest card login, plus-action return, empty results, and editable transcript.
- [ ] Run `node --test tests/test_marketplace_ui.mjs`; confirm failures.
- [ ] Build the query-first homepage and card grid, signed in header/wallet link, and plus action.
- [ ] Bind the existing recognition controller. Start only on a user gesture, preserve typed text, stop before navigation/submit, and retain ordinary text entry.
- [ ] Render blurred guest placeholders without embedding real author identity in attributes or client state.
- [ ] Build the private draft editor from current story/import controls, with preview, price, submit status, and no fake approval/reward.
- [ ] Link guest card/more and unauthenticated plus actions to server resume intents.
- [ ] Keep body access fail-closed until Phase 3 entitlement enforcement. In this intermediate build only owners/admins can preview private stories.
- [ ] Run Node tests, existing dictation/import tests, and Flask response-contract tests.
- [ ] Manually verify desktop/mobile layout and keyboard focus using synthetic data; do not activate microphone capture without the user's intended voice test.

## Handoff gate

- [ ] Guest/locked payloads contain only approved card fields.
- [ ] No private owner corpus is queried globally.
- [ ] Index failures preserve prior usable data and report truthful mode.
- [ ] Query/editor login returns are intact.
- [ ] Paid unlock and live approval remain gated for the following phases.
