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

- [ ] Three Codex threads created and started; record their IDs below.
- [ ] Reliability repair reviewed and integrated.
- [ ] Foundation/contracts reviewed and integrated with native PostgreSQL results.
- [ ] Reader/writer UI reviewed and integrated.
- [ ] Remaining publishing/search backend completed against the shared foundation.
- [ ] Ledger/unlocks, manual payments, rewards/ratings dispatched after prerequisites.
- [ ] Full acceptance and live-configuration gates verified before release.

Thread IDs, commit IDs and verification results will be added as work progresses. A running thread is not a completed deliverable.
