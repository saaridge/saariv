# Marketplace implementation progress

**Plan:** [Experience marketplace](2026-10-21-experience-marketplace.md)

**Authorization:** User requested implementation with multiple Codex threads on 2026-10-21.

**Integration branch:** `codex/experience-marketplace`.

## First batch

| Workstream | Branch / isolated worktree | Scope |
| --- | --- | --- |
| RAG reliability | `codex/marketplace-rag-baseline` / `.worktrees/marketplace-rag` | Phase 0: preserve sources and citation fidelity, repair baseline and provider tests. |
| Accounts and authentication | `codex/marketplace-foundation-auth` / `.worktrees/marketplace-foundation` | Phase 1: PostgreSQL boundary/contracts, accounts, sessions, OAuth, migration and tests. |
| Reader and author interface | `codex/marketplace-reader-writer-ui` / `.worktrees/marketplace-ui` | Phase 2 frontend: query/dictation cards, author editor, safe rendering and controller tests. |

Each thread owns its branch and only its assigned files. No thread pushes, deploys, changes real payment state, or reads/prints embedding credentials. Results are committed locally with test evidence for later integration. The coordinator owns integration, PostgreSQL dev setup, and later phase dispatch.

## Baseline

- Default remote branch: `main`, current baseline `db656ae`; no `master` exists.
- Python: 55 tests; eight failures and four errors recorded in `/private/tmp/saariv-marketplace-baseline-20261021.log`. Repair is explicitly assigned to the reliability thread.
- JavaScript: 23 tests passed on 2026-10-21 with `/opt/homebrew/bin/node --test tests/*.mjs` before the checkpoint.
- No Docker. Existing `.env`, private profiles, databases and API credentials are excluded from checkpoints/worktrees.

## Shared decisions

- Ruling: use command-line Git worktrees for the nested Saariv repository. The native tool targets the registered empty parent repository and rejected the Saariv commit as an invalid reference. All worktrees stay under the ignored `.worktrees/` directory.
- Ruling: parallelize reliability, foundation, and frontend work first. Publishing/search backend, ledger/unlocks, manual payments, rewards/ratings retain the roadmap dependency order; no duplicate database foundation is created by a downstream thread.
- Ruling: the interface thread owns new marketplace templates/scripts/styles only. It does not change `app.py`, core contracts, or legacy dictation controllers. The reliability thread may repair existing `app.py` evidence rendering; the coordinator adds marketplace registration later.
- Foundation exports `marketplace.db.Base`, a `Database` wrapper with `session_factory` and `transaction()` context manager, and the master-plan DTOs. Its minimal stable contract is checkpointed first so downstream work can depend on it.

## Dispatch and integration evidence

- [x] Three Codex threads created and started from checkpoint `33c6553`.
- [x] Reliability repair reviewed and integrated from `codex/marketplace-rag-baseline`.
- [x] Foundation/contracts reviewed and integrated from `codex/marketplace-foundation-auth`, with native PostgreSQL results.
- [x] Reader/writer UI reviewed and integrated from `codex/marketplace-reader-writer-ui`.
- [ ] Remaining publishing/search backend completed against the shared foundation.
- [ ] Ledger/unlocks, manual payments, rewards/ratings dispatched after prerequisites.
- [ ] Full acceptance and live-configuration gates verified before release.

### Created threads

- RAG reliability: `01a15f06-41b9-7480-90b3-163e7615c156`.
- Accounts/social login: `01a15f06-554c-7f93-999f-a74892849232`.
- Reader/author interface: `01a15f06-66a8-78f1-8a7f-ea3cfdfa39c6`.

### Native database setup

PostgreSQL 16.11 is running on `127.0.0.1:55432` with a dedicated synthetic-data database `saariv_marketplace_test`, user `saariv_dev`. Verified with PostgreSQL's own client on 2026-10-21. The cluster data and logs are ignored under `.local-dev/postgres/`; it does not use an existing application database.

Test URL: `postgresql+psycopg://saariv_dev@127.0.0.1:55432/saariv_marketplace_test`.

The local cluster binds only to loopback and is for synthetic test data. No existing application environment file was modified. Tests must still enforce isolated schemas/cleanup and refuse non-test database names.

Commit IDs and verification results will be added as work progresses. A running thread is not a completed deliverable.

## Integrated local run and verification — 2026-10-21

The integration branch now contains all three completed first-batch workstreams.
Runtime registration mounts the new homepage, social login page and private editor;
the existing `/try` route remains available. First-person display now consumes
`display_text` while raw citation text/offsets stay unchanged.

- Fresh combined Python suite: **114 passed**, including five real-entry-point runtime tests.
- Fresh combined Node suite: **53 passed**, including the citation presentation regression.
- Python compilation and `git diff --check`: passed.
- Native Flask is running at `http://127.0.0.1:8080`, with debugger/reloader disabled.
- Separate development database: `saariv_marketplace_dev`, migration `001_accounts_sessions` applied. The application never uses the disposable test database.
- Live browser: homepage and `/try` load; Add experience redirects to `/login?next=%2Fexperiences%2Fnew`.
- Live private RAG: one synthetic story imported with real configured embeddings in hybrid mode; retrieval returned one hit; another browser session was denied (401); playground returned one cited extractive answer; the synthetic story was deleted through its owning session.
- No live Google, LinkedIn or Facebook login was attempted: all three provider applications are unconfigured locally.

Public marketplace search, persisted publishing, entitlements, wallet, payments,
rewards and ratings remain incomplete. Pending operations return an explicit 503
instead of fake results, balances, saves or purchases. Passing the first-batch
suites does not establish the full marketplace acceptance gate.

Runtime instructions and detailed evidence: [local testing report](../../marketplace-local-testing.md).
