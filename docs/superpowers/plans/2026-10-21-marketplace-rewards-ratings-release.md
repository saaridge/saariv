# Marketplace Rewards, Ratings, and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this subsystem task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete funded publication approval, author ratings, and verification of the entire marketplace before enabling it.

**Architecture:** First approval publishes a revision, transfers ten coins from the reward treasury, records a unique grant, and enqueues indexing in one SQL transaction. Entitled-reader votes update author aggregates. Final acceptance includes live provider setup, synthetic money flows, and recovery tests.

**Tech Stack:** Existing Flask/PostgreSQL/ledger/outbox, unittest, node:test, native Qdrant, held-out retrieval evaluator.

**Spec:** [Marketplace design](../specs/2026-10-21-experience-marketplace-design.md)

**Roadmap:** [Master plan](2026-10-21-experience-marketplace.md)

**Prerequisite:** Phases 1–4 implemented and verified.

## Global Constraints

- Ten coins only for a new approved experience; drafts, edits, retries, and duplicate submissions do not earn again.
- Publication reward coins are spendable and withdrawable under the same confirmed rule.
- Reward treasury must be funded. No negative treasury or approval that promises an unpaid reward.
- Valid votes require an entitlement; no self-votes or coin rewards for voting.
- Author rating sorts relevant results, not all published experiences.
- Development never performs actual external payments/payouts.

## Review Focus

Approval/reward/index-job atomicity; exhausted treasury and admin races; duplicate copies under new IDs; rating switch/remove correctness; complete privacy and return navigation; actual vs simulated acceptance evidence.

## Task 5.1: Funded approval and exact once publication reward

**Files:** Create `marketplace/reputation/models.py`, `rewards.py`, `admin.py`; migration `005_reputation_rewards.py`; `templates/admin/reviews.html`; `tests/test_marketplace_rewards.py`.

**Interface:** `ApprovalService.approve_experience(admin_id, revision_id, idempotency_key) -> ApprovalReceipt`.

**Schema:** Unique reward grant per experience, approved content fingerprints by author/hash/canonical experience, funded treasury references, review decisions, votes and author aggregate schema for Task 5.2.

**Test anchor:** `test_first_approval_posts_ten_once` starts treasury at 100 and author at zero, then asserts treasury 90, author 10, one grant, one index job, and published revision after concurrent approval/replay; `test_empty_treasury_keeps_submission_unapproved` asserts no publication/grant/job.

- [ ] Write failing tests for first funded approval, insufficient treasury, concurrent approvals, retry with another key, edits/resubmission, cloned content under a new experience ID, and rollback after each financial/domain step.
- [ ] Run `python -m unittest discover -s tests -p 'test_marketplace_rewards.py' -v`; confirm failures.
- [ ] Implement operator-funded treasury entries with verified budget references and audit. Keep external funding records distinct from public reward grants.
- [ ] Implement normalized body fingerprints independent of title/price. Preserve fingerprints for all approved revisions, so cloning an edited version cannot bypass the original grant check.
- [ ] Flag near duplicates for human review. Reject or merge duplicate submissions into their canonical experience before approval; do not approve a second reward-eligible copy.
- [ ] Implement first approval as one transaction: lock submission/accounts, validate eligibility and funds, set published/current approved revision, post ten coin treasury-to-author transfer, insert unique grant/fingerprint/audit, enqueue unique index job.
- [ ] Implement later revision approvals with updated fingerprints/outbox but no new reward. If funding is unavailable for a first approval, leave it awaiting review and return an actionable status.
- [ ] Render treasury balance, eligibility, duplicate evidence, approve/reject reason, and index state in the protected review queue.
- [ ] Run PostgreSQL concurrency/rollback tests and verify that reward coins appear in wallet history and withdrawable balance.

## Task 5.2: Reader voting and author rating

**Files:** Create `marketplace/reputation/service.py`; extend reputation routes/admin registration, search service and experience UI; `tests/test_marketplace_ratings.py`, `tests/test_marketplace_rating_ui.mjs`.

**Interface:** `VoteService.set_vote(reader_id, experience_id, value) -> AuthorRating`, value -1/0/+1.

**Test anchor:** `test_vote_switch_and_remove_have_exact_counts` asserts counts 1/0 after +1, 0/1 after -1, 0/0 after 0, and neutral score 0.5; repeating any operation does not change counts again.

- [ ] Write failing tests for entitlement requirement, self-vote denial, one vote per experience/reader, repeated same vote, switch/remove, concurrency, and audited invalid-vote correction.
- [ ] Add search fixtures proving a highly rated unrelated author is filtered out before ranking and a new author is represented honestly.
- [ ] Run rating tests and confirm failures.
- [ ] Implement transactional vote upsert/delete and nonnegative author aggregate updates; include valid votes on archived approved experiences.
- [ ] Compute ranking score `(upvotes + 2) / (upvotes + downvotes + 4)`. Display actual helpful count/ratio separately; no synthetic reviews from the prior.
- [ ] Apply rating order to already-qualified search candidates, followed by relevance and stable experience ID. Preserve snapshot paging consistency.
- [ ] Add accessible up/down/remove controls to unlocked detail pages; show persisted vote and refreshed author rating, with retry-safe UI.
- [ ] Run rating/search/entitlement suites together and inspect locked/guest responses for rating-related identity leaks.

## Task 5.3: Retrieval evaluation and operational visibility

**Files:** Create `marketplace/evaluate.py`, `evals/marketplace-retrieval.json`, `tests/test_marketplace_evaluation.py`; add admin metrics to reconciliation/index views.

**Test anchor:** `test_single_relevant_result_at_rank_two` asserts Recall@2 = 1 and MRR = 0.5; `test_irrelevant_high_rating_never_enters_results` separates the relevance gate from author ordering.

- [ ] Write failing metric tests using small known examples for Recall@k, MRR, nDCG, no-answer errors, and rating-order correctness.
- [ ] Run evaluator tests and confirm failures.
- [ ] Implement disposable-corpus evaluation without real money effects. Separate relevance recall from the policy that sorts by author score.
- [ ] Label at least 50 representative typed/dictated queries, paraphrases, author/topic queries, and unknown questions. Split tuning examples from held-out acceptance examples.
- [ ] Compare lexical, dense, and hybrid retrieval; tune chunk size, overlap, candidate count, fusion, and relevance cutoff only on the tuning split.
- [ ] Report held-out quality, latency p50/p95, embedding/chat usage and fallback rate; do not substitute click/unlock conversion for relevance.
- [ ] Add indexing lag/retry metrics, pending request age, treasury spending, ledger reconciliation variance, and privacy/access-denial diagnostics without logging story bodies or payout details.
- [ ] Publish actual measurements against proposed targets; record failures and remaining setup instead of declaring a target achieved.

## Task 5.4: End-to-end scenarios, migrations, and operator runbook

**Files:** Create `tests/test_marketplace_end_to_end.py`, `docs/marketplace-operations.md`; update `README.md`, `.env.example`; extend UI tests as needed.

- [ ] Write end-to-end cases with synthetic users/content/transfers for every row in the acceptance matrix below.
- [ ] Verify guest search → login → exact card → explicit unlock; direct plus → login → original editor; pending recharge → credit → original preview → explicit purchase.
- [ ] Verify publication → funded reward → searchable cards → reader purchase → author earnings → withdrawal reserve/settle/reject history.
- [ ] Verify all ownership/entitlement boundaries across page/API/agent routes, hidden DOM, structured metadata, stale search hits, and export/download paths.
- [ ] Rehearse database migration from the pre-marketplace app while leaving private SQLite/profile data intact. Verify explicit legacy ownership claim and backups/restore.
- [ ] Rehearse worker crash/retry, Qdrant outage, GPT outage, provider profile rebuild failure, duplicate admin request, and uncertain payout reconciliation.
- [ ] Document native PostgreSQL/Qdrant setup and worker/web commands, provider callback configuration, administrator roles, treasury funding, manual verification, payout reconciliation, and compensating corrections.
- [ ] Test all three actual provider logins in supported browsers when operator applications are configured. Missing live provider checks block launch while deterministic tests can still pass.
- [ ] Run the full Python suite, all Node suites, evaluator, compilation, and `git diff --check` using the master plan commands.
- [ ] Review the complete implementation against the design; fix concrete defects and rerun only the affected gates plus required full suite.
- [ ] Enable the marketplace feature flag only after the acceptance gates and required operator inputs are satisfied. Publishing/deployment still follows the user's authorization.

## Acceptance matrix

| Scenario | Required evidence |
| --- | --- |
| Guest types or dictates a query | Up to four cards; concealed identity absent from payload, editable transcript, clear empty/error states. |
| Guest clicks card/more | Social login starts; selected query/experience survives; no coins move. |
| Authenticated search | Relevant cards show real author ratings, prices, ownership, stable rating order. |
| Author uses plus | Auth guard returns to editor; private draft and source ownership preserved. |
| First publication | Admin approval + ten funded coins + unique grant + index outbox commit together. |
| Edit/duplicate/retry | No second publication reward; rejected copies have no financial effects. |
| Paid unlock with enough coins | One debit, one author credit, one entitlement; refresh and parallel retries add no charge. |
| Insufficient funds | Recharge quote and pending transfer request; admin credit once; return to same experience; explicit purchase still required. |
| Vote | Entitled reader only; switch/remove updates author aggregate once; self-vote denied. |
| Withdrawal | All coin sources eligible; minimum/increment/reserve rule; no spend of reserved funds; exact once release/settlement. |
| Provider/index/bank uncertainty | Honest status, no lost prior data, no duplicate external payout, no hidden financial mutation. |
| Operation and privacy | Zero reconciliation variance; backups/restoration; no private/deliberately concealed fields in public outputs. |

## Completion record to fill during implementation

- Baseline repairs and final Python/Node counts:
- PostgreSQL/Qdrant versions and actual concurrency results:
- Live Google / LinkedIn / Facebook results:
- Retrieval quality and latency measurements:
- Synthetic recharge, purchase, reward, payout scenario receipts:
- Migration/restore and reconciliation evidence:
- Unresolved operator setup or product-policy decisions:
- Review findings and corrections:

Do not fill these with assumed success during planning.
