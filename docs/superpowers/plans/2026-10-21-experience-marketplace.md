# Experience Marketplace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Saariv into an experience marketplace with query/dictation discovery, social sign-in, paid permanent unlocks, author ratings, manual recharge/payout, and funded publication rewards.

**Architecture:** Extend Flask/Jinja and the existing private RAG. Add PostgreSQL domain records and an immutable balanced coin ledger. Use an isolated published Qdrant collection with SQL-authoritative visibility checks and an outbox worker. Keep existing embedding and chat providers independently configurable.

**Tech Stack:** Python/Flask, SQLAlchemy 2, Alembic, psycopg 3, Authlib, PostgreSQL, existing qdrant-client, native Qdrant server for shared processes, vanilla JavaScript, unittest, node:test.

**Spec:** [Marketplace design](../specs/2026-10-21-experience-marketplace-design.md)

**Status:** Implementation authorized on 2026-10-21 using multiple Codex threads. Track the first batch in [the progress ledger](2026-10-21-marketplace-progress.md); checkboxes remain open until their evidence is recorded.

## Global Constraints

- Keep native development; no Docker/Testcontainers.
- Latest remote branch is `main`, not `master`; verified at `db656ae` on 2026-10-21. Preserve local voice work in `README.md`, `static/css/styles.css`, `static/js/main.js`, `templates/try.html`, `tests/test_story_import.mjs`, `static/js/story-dictation.js`, and `tests/test_story_dictation.mjs`.
- Keep private owner filtering, raw source evidence/citations, taxonomy-only Prompt 1, and narrative Prompt 2.
- Use the supplied embedding configuration only for embeddings; continue using the existing chat model for GPT work. Never print or commit secrets.
- Confirmed: permanent unlock, all purchased/earned/reward coins withdrawable, ten coins once per approved new experience, withdrawals in 100 coin increments with minimum 100 and ten left available at reservation.
- Proposed: USD 1 = 100 coins; no platform fee initially; four guest cards; 12 signed in cards; review before publication; funded rewards.
- PostgreSQL is required for ledger/concurrency tests. SQLite is not a substitute and missing test database configuration must fail the gate, not silently skip it.
- No real external transfers during development verification. Live provider setup and real money launch are separate operational gates.
- Do not release partial paid flows. Use a server feature flag until all accounting, approval, privacy, and navigation gates pass.

## Review Focus

- A guest or locked reader must never receive full story text or concealed author identity.
- Private avatar data must not be exposed by widening existing knowledge search.
- First approval must publish, grant ten funded coins once, and enqueue indexing atomically.
- Concurrent purchases, approvals, rewards, and withdrawals must not overspend or double-post.
- Repeated visits are free after one successful purchase.
- External payout ambiguity must not trigger a second bank transfer.
- Login and payment review must restore the exact experience/query without automatically spending coins.
- Dense-index failures and GPT outages must preserve source data and truthfully report retrieval mode.

## 1. Baseline evidence and execution order

Fetched `origin` and checked remote refs by command line. There is no `master`, and no newer `main` commit than the current base. The existing dictation edits were not stashed, reset, or overwritten.

Fresh baseline command:

```sh
.venv-rag/bin/python -m unittest discover -s tests -v
```

Observed: 55 tests, eight failures, four errors. Local diagnostic log: `/private/tmp/saariv-marketplace-baseline-20261021.log`. This is a baseline to repair, not a passing gate.

| Phase | Focus and handoff | Dependency |
| --- | --- | --- |
| 0–1 | [Reliability, database, accounts, social login](2026-10-21-marketplace-foundation-auth.md) | Current source plus preserved dictation. |
| 2 | [Private drafts, published retrieval, homepage](2026-10-21-marketplace-publishing-search.md) | Account/principal and database contracts. |
| 3 | [Ledger, wallet, permanent paid unlocks](2026-10-21-marketplace-wallet-unlocks.md) | User and experience/revision schema. |
| 4 | [Manual recharge and withdrawal](2026-10-21-marketplace-manual-payments.md) | Ledger and purchase return-intent contracts. |
| 5 | [Funded approval rewards, votes, end-to-end release](2026-10-21-marketplace-rewards-ratings-release.md) | Publication, wallet, and manual admin patterns. |

Run these in dependency order. Draft search fixtures may insert approved examples into the isolated test database before Phase 5; production cannot publish without the final funded approval service.

## 2. Planned file map

Paths below are repository-relative; all are planned additions unless marked existing.

| Files | Responsibility |
| --- | --- |
| `marketplace/__init__.py`, `config.py`, `db.py`, `contracts.py`, `security.py` | Blueprint registration, environment settings, SQL session/transactions, shared DTOs, principal/CSRF/role helpers. |
| `marketplace/accounts/{models,service,oauth,routes}.py` | Users, identities, sessions, resume intents, provider callbacks, explicit account linking. |
| `marketplace/experiences/{models,service,imports,routes}.py` | Draft/revision ownership, import bridge, approved content serialization, authoring. |
| `marketplace/search/{service,index,worker,routes}.py` | Query assistance, hybrid candidates, SQL visibility checks, safe card DTOs, outbox processing. |
| `marketplace/wallet/{models,ledger,purchases,routes}.py` | Balanced ledger, wallet projections, purchase quotes, entitlements, read authorization. |
| `marketplace/payments/{models,service,withdrawals,routes,admin}.py` | Recharge quotes/verification, withdrawal reservations and settlement, owner/admin APIs. |
| `marketplace/reputation/{models,service,rewards,admin}.py` | Votes/author aggregates, funded approval, duplicate reward prevention, review queues. |
| `migrations/`, `alembic.ini` | Reversible schema migrations and deployment gates. |
| `templates/marketplace/{home,login,editor,experience,wallet,request}.html` | Reader/writer/wallet pages. |
| `templates/admin/{reviews,recharges,withdrawals,reconciliation}.html` | Protected review and manual financial queues. |
| `static/js/{marketplace,authoring,wallet}.js` | Query/dictation, editor, unlock, request status/resume UI. |
| `app.py` (existing), `requirements.txt` (existing), `.env.example` (existing) | Register domains, pinned dependencies, non-secret configuration. |
| `knowledge/{service,store,onboarding,answers}.py` (existing as needed) | Phase 0 data-preservation fixes; remote Qdrant support only where shared published indexing needs it. |
| `static/js/story-dictation.js` (existing local work) | Shared microphone controller; avoid duplicating speech recognition logic. |
| `tests/marketplace_fixtures.py`, `tests/test_marketplace_*.py`, `tests/test_marketplace_*.mjs` | Native PostgreSQL and browser-controller coverage using synthetic data. |
| `evals/marketplace-retrieval.json`, `marketplace/evaluate.py` | Held-out relevance/rating evaluation with no payment side effects. |
| `docs/marketplace-operations.md`, `README.md` (existing) | Native setup, migrations, OAuth, manual queues, reconciliation, recovery. |

## 3. Shared interfaces

Define these in `marketplace/contracts.py` before writing cross-domain code. All services derive authority from a server-built principal, not an arbitrary request user ID.

### Data contracts

- `Principal(user_id: UUID | None, roles: frozenset[str])`
- `ExperienceCard(experience_id, title, teaser, taxonomy, price_coins, author, rating, unlocked)`: allowlisted fields only. Guest `author` is null; no raw content, source references, or hidden author identifiers.
- `SearchPage(query_id, items, next_cursor, login_required, retrieval_mode)`
- `WalletSnapshot(available_coins, reserved_coins, withdrawable_coins)`
- `UnlockReceipt(entitlement_id, experience_id, charged_coins, available_coins)`: replay returns the original receipt; a fresh request for an already-owned experience reports zero new charge and references its entitlement.
- `RequestReceipt(request_id, status, coins, fiat_minor, currency, next_path)`
- `ApprovalReceipt(experience_id, revision_id, reward_transaction_id, index_job_id)`
- `AuthorRating(upvotes, downvotes, ranking_score)`

### Service signatures

```python
SearchService.search(*, principal: Principal, query: str,
                     cursor: str | None = None) -> SearchPage

ExperienceService.submit(*, author_id: UUID,
                         draft_id: UUID) -> ExperienceRevision

LedgerService.post_transfer(session: Session, *, kind: str,
    debit_account_id: UUID, credit_account_id: UUID, coins: int,
    idempotency_key: str, metadata: dict) -> LedgerTransaction

UnlockService.unlock(*, user_id: UUID, experience_id: UUID,
    quote_id: UUID, idempotency_key: str) -> UnlockReceipt

FundingService.approve_recharge(*, admin_id: UUID, request_id: UUID,
    bank_reference: str, idempotency_key: str) -> RequestReceipt

WithdrawalService.request(*, user_id: UUID, coins: int,
    payout_destination_id: UUID, idempotency_key: str) -> RequestReceipt

WithdrawalService.settle(*, admin_id: UUID, request_id: UUID,
    payout_reference: str, idempotency_key: str) -> RequestReceipt

ApprovalService.approve_experience(*, admin_id: UUID, revision_id: UUID,
    idempotency_key: str) -> ApprovalReceipt

VoteService.set_vote(*, reader_id: UUID, experience_id: UUID,
                    value: int) -> AuthorRating
```

`LedgerService.post_transfer` validates/posts inside the caller's SQL transaction and never commits internally. Domain services own the transaction that combines ledger, entitlement/request/approval, and audit records. Database errors roll all of them back together.

All money writes have operation references in addition to HTTP idempotency keys. An operation is unique even when a caller generates a second key.

## 4. Route contract

| Route | Access and behavior |
| --- | --- |
| `GET /` | Query UI, microphone, plus action; safe empty/search state. |
| `GET /login` | Three providers and opaque resume intent; no fake login when unconfigured. |
| `GET /auth/login/<provider>`, `GET /auth/callback/<provider>` | Provider allowlist, state/nonce validation, session rotation, internal resume. |
| `POST /auth/logout` | Revoke session; CSRF required. |
| `POST /api/search` | Guest or reader; guest hard cap four and redacted identity, authenticated page size/cursor. Same-origin query-only endpoint, no payment mutation. |
| `GET /experiences/new` | Account required; login returns here. |
| `POST /api/experiences/drafts`, `PATCH /api/experiences/drafts/<id>`, `POST .../<id>/submit` | Author only, version checks, CSRF. |
| `GET /experiences/<id>` | Guests go to login; authenticated locked preview or authorized full page. |
| `GET /api/experiences/<id>/content` | Author, permitted admin, or entitled reader only. |
| `POST /api/experiences/<id>/quote`, `POST .../<id>/unlock` | Reader only; server price, current quote, idempotency; never charge on GET. |
| `PUT /api/experiences/<id>/vote` | Entitled reader, value -1/0/+1, no self-vote. |
| `GET /wallet`, `GET /api/wallet`, `GET /api/wallet/transactions` | Own available/reserved balance and history only. |
| `POST /api/wallet/recharges`, `POST .../<id>/submitted` | Own quote/request; submitting a claim never credits coins. |
| `GET /wallet/requests/<id>`, `GET /api/wallet/requests/<id>` | Own request, status timeline, validated return link. |
| `POST /api/wallet/withdrawals`, `POST .../<id>/cancel` | Own destination; reserve/release according to state and confirmed rule. |
| `POST /api/admin/experiences/<revision_id>/approve` or `/reject` | Admin; first approval posts funded reward and index job atomically. |
| `POST /api/admin/recharges/<id>/approve` or `/reject` | Admin, verified unique incoming transfer reference. |
| `POST /api/admin/withdrawals/<id>/start`, `/settle`, `/reject` | Admin; payout outside SQL transaction, verified unique outgoing reference on settlement. |
| `POST /api/admin/reward-budget/fund` | Admin; verified funding record and balanced treasury entry. |
| `GET /admin/reviews`, `/recharges`, `/withdrawals`, `/reconciliation` | Admin only; no direct balance editor. |

All state-changing browser routes require CSRF, authenticated actor/role as appropriate, strict input validation, and request-size limits. Search is separately rate-limited for guest embedding/GPT cost. Structured errors distinguish login required, access denied, insufficient coins, stale quote, invalid transition, reconciliation needed, and provider unavailable.

## 5. Configuration and native execution

Planned variables (placeholders only in `.env.example`):

- `DATABASE_URL`, `TEST_DATABASE_URL`, `MARKETPLACE_ENABLED`, application/session secret settings.
- Provider client IDs/secrets and public callback base URL for Google, LinkedIn, Facebook.
- `QDRANT_URL` and optional API key for shared mode; retain isolated local paths for private development and disposable tests.
- Existing embedding settings and existing chat settings; do not reuse one API key automatically for the other purpose.
- Currency/rate, ten coin reward, 100 coin withdrawal unit/minimum, ten coin reserve rule, quote expiry, guest cap.
- Administrator payment instructions and payout configuration supplied privately; no banking details committed.

Native setup will document a local PostgreSQL service, schema migration, Flask run, and separate outbox worker command. Test helpers must reject the application's non-test database and require an explicitly provisioned disposable database.

Planned verification commands after their modules exist:

```sh
.venv-rag/bin/python -m unittest discover -s tests -v
node --test tests/*.mjs
.venv-rag/bin/python -m marketplace.evaluate --dataset evals/marketplace-retrieval.json
.venv-rag/bin/python -m compileall -q app.py knowledge marketplace
git -c core.fsmonitor=false diff --check
```

`TEST_DATABASE_URL` must already be configured for the Python command. Commands above are future acceptance commands, not evidence they passed during planning.

## 6. Completion checklist

- [ ] Phase 0 baseline repaired with justified test expectation updates.
- [ ] Accounts, identity linking, ownership migration, and resume intents verified.
- [ ] Private drafts cannot appear in published search.
- [ ] Guest/locked response contracts verified against full body/identity leaks.
- [ ] Native PostgreSQL ledger and concurrency tests pass.
- [ ] Unlock transfers and permanent entitlements verified under retries.
- [ ] Manual recharge/payout state machines, reservations, and audit verified.
- [ ] First publication awards ten funded coins exactly once, duplicate submissions do not mint rewards.
- [ ] Author voting/rating ordering verified after relevance filtering.
- [ ] All three actual provider logins verified or release explicitly held for missing setup.
- [ ] End-to-end typed/dictated read/write/recharge/withdraw scenarios pass with synthetic payments.
- [ ] Migration/restore, index retry, and ledger reconciliation rehearsed.
- [ ] Final review distinguishes measured results from targets and configured services from simulations.

## 7. Planning self-review

This roadmap accounts for all requested read/write/authentication/coin/recharge/withdrawal/manual payment flows and all four explicit follow-up business decisions. Remaining operator inputs are listed in the design's launch section; none prevents creating the local architecture and deterministic tests. The user has authorized implementation across multiple Codex threads; independent first-batch work is isolated by Git worktree and later financial phases retain their dependency gates.
