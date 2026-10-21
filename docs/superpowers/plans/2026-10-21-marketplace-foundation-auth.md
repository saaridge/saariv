# Marketplace Foundation and Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this subsystem task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the current RAG baseline, then establish native PostgreSQL, shared contracts, secure accounts, three social providers, and safe return navigation.

**Architecture:** Add a modular Flask marketplace package. Use PostgreSQL-backed identities/sessions and Authlib. Preserve private browser-owned RAG and link it only with signed-cookie proof.

**Tech Stack:** Existing Python/Flask, SQLAlchemy 2, psycopg 3, Alembic, Authlib, unittest, node:test.

**Spec:** [Marketplace design](../specs/2026-10-21-experience-marketplace-design.md)

**Roadmap:** [Master plan](2026-10-21-experience-marketplace.md)

**Prerequisite:** Current source at `db656ae` with local dictation work preserved.

## Global Constraints

- Work natively. Never replace the current dirty checkout or expose environment credentials.
- Repair actual data-preservation defects; update stale tests only when the newer confirmed behavior requires it.
- Social identity is provider + subject. Email matching does not merge wallets.
- A prototype owner cookie is not a marketplace account or payment identity.
- No implementation has been performed as part of this planning deliverable.

## Review Focus

Failed imports must not destroy working data; citations must remain exact. OAuth state/nonce/session boundaries, return URL validation, missing provider email, and explicit ownership claims need negative tests.

## Task 0.1: Classify and repair the current RAG baseline

**Files:** Existing `knowledge/service.py`, `knowledge/store.py`, `knowledge/onboarding.py`, `knowledge/answers.py`, `app.py`; existing `tests/test_knowledge_service.py`, `test_knowledge_providers.py`, `test_knowledge_answers.py`, `test_experience_story.py`, `test_knowledge_api.py`.

**Evidence:** `/private/tmp/saariv-marketplace-baseline-20261021.log`: 55 tests, eight failures, four errors. It includes disabled profile compatibility checks, replacement before successful preparation, and provider mocks that no longer accept the SSL context argument.

**Test anchor:** Extend `test_failed_import_preserves_previous_source_and_vectors`: a provider failure raises `ProviderError`, the old source text is unchanged, and its previous search hit remains present. Extend `test_equal_dimensions_do_not_allow_mixing_model_profiles`: same dimensions with a different profile raises `ReindexRequired` before deletion.

- [ ] Record each failure as a behavior defect or a stale assertion using current code and the earlier confirmed narrative/first-person requirements.
- [ ] Add/adjust focused regression cases for invalid story input, failed first import, failed replacement, failed rebuild, equal-dimension/different-model profiles, and exact citation spans.
- [ ] Run each failing module separately with `python -m unittest discover -s tests -p 'test_knowledge_service.py' -v` (and the corresponding filename for other modules); confirm the regression is reproduced before patching.
- [ ] Prepare source/chunk/vector generations without deleting prior data. Publish only after validation succeeds; retain the usable generation on failure.
- [ ] Make missing dense retrieval explicit and keep the reported mode truthful. Do not modify the shared provider object to silently switch every owner to lexical mode.
- [ ] Validate narrative input before ingest; return appropriate client errors for empty/headings-only input.
- [ ] Keep raw `source.text` and offsets intact; put first-person presentation in a separate display/answer field.
- [ ] Update HTTP mock signatures for actual TLS/context behavior without disabling verification. Preserve semantic tests for grounding, vector order, and query/document roles.
- [ ] Run the full Python suite and existing Node tests; record actual output. Do not proceed to financial code while unexplained baseline failures remain.

## Task 1.1: Database boundary, configuration, and contracts

**Files:** Create `marketplace/__init__.py`, `config.py`, `db.py`, `contracts.py`, `security.py`; `migrations/env.py`, `alembic.ini`, `tests/marketplace_fixtures.py`, `tests/test_marketplace_foundation.py`. Modify `requirements.txt`, `.env.example`, `app.py`.

**Interfaces:** Shared DTOs/service signatures in the master plan; `register_marketplace(app)`, scoped database session, transaction context, server-built principal.

**Test anchor:** `test_transaction_rolls_back_domain_and_projection`: an exception after a synthetic write leaves both records absent; `test_guest_card_contract_has_no_content_or_author_identifier`: the serialized card has no raw body/source fields and `author is None`.

- [ ] Write failing configuration/contract tests for absent database URL, weak/default production signing secrets, secret redaction, transaction rollback, DTO safe serialization, and production cookie requirements.
- [ ] Write the database test helper: require `TEST_DATABASE_URL`, reject the configured application database and non-test database names, create isolated test schema/data, clean up only that test namespace.
- [ ] Run `python -m unittest discover -s tests -p 'test_marketplace_foundation.py' -v`; confirm missing module/behavior failures.
- [ ] Pin compatible stable dependency versions and create the database/session lifecycle and feature-flag registration.
- [ ] Implement the agreed DTOs and error schema. Keep request/response serialization separate from ORM records.
- [ ] Test migration upgrade on an empty native PostgreSQL test database and rollback/upgrade before adding any real data.
- [ ] Run the foundation tests with native PostgreSQL and the baseline suite.

## Task 1.2: Account schema and authenticated sessions

**Files:** Create `marketplace/accounts/models.py`, `service.py`, `routes.py`; migration `001_accounts_sessions.py`; `tests/test_marketplace_accounts.py`.

**Schema:** Users, provider identities, server sessions, resume intents, private owner links, audit events. Unique(provider, subject), unique(private owner), revocable opaque session IDs.

**Test anchor:** `test_same_email_does_not_link_provider_subjects` asserts distinct user IDs; `test_arbitrary_owner_id_cannot_claim_private_data` expects HTTP 403 with no owner-link row.

- [ ] Write failing tests for identity uniqueness, same-email/different-subject isolation, session rotation/revocation, role enforcement, CSRF failures, and request ID spoofing.
- [ ] Run the account tests and confirm failures.
- [ ] Implement account creation and server-side session lookup. Derive user ID/roles only from the validated session.
- [ ] Implement explicit identity linking that requires an authenticated account and a fresh provider proof; conflicting existing ownership is rejected.
- [ ] Implement single-use private-owner claiming with signed-cookie proof. Reject arbitrary owner/profile IDs.
- [ ] Implement opaque expiring resume intents for search/experience/editor. Validate internal destinations and preserve safe query data server-side.
- [ ] Verify return-intent ownership, expiry, open-redirect rejection, and no session/story data in URLs.
- [ ] Run account tests on PostgreSQL plus existing owner-isolation tests.

## Task 1.3: Real provider adapters and login page

**Files:** Create `marketplace/accounts/oauth.py`, `templates/marketplace/login.html`; extend accounts routes/config; `tests/test_marketplace_oauth.py`.

**Routes:** `/auth/login/<provider>`, `/auth/callback/<provider>`, `POST /auth/logout`, `/login`.

**Test anchor:** `test_linkedin_without_email_signs_in_by_subject` creates one account and consumes its internal resume intent; `test_callback_with_wrong_state_creates_no_session` asserts no authenticated session after the error.

- [ ] Write failing provider adapter tests for state mismatch, nonce mismatch, invalid issuer/audience/expiry, denied consent, missing email, unknown provider, callback replay, and explicit linking.
- [ ] Run the OAuth tests and confirm failures.
- [ ] Add Authlib Google/LinkedIn OIDC configuration using discovery metadata; map stable subjects, not email.
- [ ] Add Facebook login using the current official provider setup; verify its live supported Graph version during implementation.
- [ ] Render three provider options with honest unconfigured/error states. Successful callbacks rotate sessions and consume the original resume intent.
- [ ] Request minimal profile scopes; avoid keeping unused tokens. If tokens must persist, encrypt them and document revocation.
- [ ] Run deterministic adapter tests without external credentials.
- [ ] With configured applications, smoke-test all three logins in a supported system browser, including consent denial and return to the selected query/editor. Record unconfigured providers as a blocked release gate, not a passing test.

## Handoff gate

- [ ] Baseline and account/contract tests pass with native PostgreSQL.
- [ ] Shared principal, DTO, error, CSRF, and transaction interfaces match the master plan.
- [ ] Existing private ownership and microphone behavior remain functional.
- [ ] Missing live OAuth configuration is listed explicitly.
- [ ] Inspect the diff for unintended voice edits or secrets; checkpoint only the intended implementation when implementation is later authorized.
