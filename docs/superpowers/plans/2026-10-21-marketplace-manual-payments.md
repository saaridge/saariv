# Marketplace Manual Recharge and Withdrawal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this subsystem task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement manual coin purchases and payouts with auditable request states, exact once posting, and return to the selected experience.

**Architecture:** SQL request state and ledger effects commit together. External bank actions remain manual, outside database transactions. Admin approval requires verified unique external references.

**Tech Stack:** Flask/Jinja, native PostgreSQL, existing ledger/principal/resume services, unittest and node:test.

**Spec:** [Marketplace design](../specs/2026-10-21-experience-marketplace-design.md)

**Roadmap:** [Master plan](2026-10-21-experience-marketplace.md)

**Prerequisite:** Phase 3 ledger, wallet, entitlement, and return-intent contracts.

## Global Constraints

- USD 1 = 100 coins is the proposed configurable starting rate, captured in each immutable quote.
- A user saying “I transferred” does not credit a wallet. Admin verifies the actual transfer.
- Withdrawal minimum 100, increments 100, leave ten available when reserving.
- Purchased/earned/reward coins are all eligible after they are posted.
- Development uses synthetic references and destinations; no actual transfer occurs.
- One-hour recharge and 24-hour payout messages are service targets, not timers that move funds.

## Review Focus

Duplicate incoming/outgoing references, stale admin pages, spend/withdraw races, unknown bank transfer outcomes, reservation release, privacy of payout data, and exact return navigation.

## Task 4.1: Request records and recharge quotation

**Files:** Create `marketplace/payments/models.py`, `service.py`; migration `004_manual_payments.py`; `tests/test_marketplace_recharges.py`.

**Schema:** Recharge/withdrawal requests, immutable coin/fiat/currency/rate quote, private payout destinations, verified fiat movement references, status events, bound resume intent.

**Test anchor:** `test_recharge_100_credits_only_after_verified_approval` asserts quote USD 100 cents, balance zero after submission, balance 100 after approval, and balance still 100 after replay/duplicate reference.

- [ ] Write failing tests for integer quotes, rate-change stability, user/request memo uniqueness, ownership, input tampering, and no credit on request creation/submission.
- [ ] Run `python -m unittest discover -s tests -p 'test_marketplace_recharges.py' -v`; confirm failures.
- [ ] Implement positive coin amount quoting with exact integer fiat calculation. Reject unsupported values/currencies rather than rounding silently.
- [ ] Persist a pending-payment request before returning payment instructions. Include logged in user ID and a unique request ID in the transfer memo.
- [ ] Add “I transferred” transition to pending review. Keep evidence private and treat it only as a review aid.
- [ ] Implement admin approval with checked amount/currency/memo, unique normalized bank reference, ledger credit from recharge clearing, request state and audit in one transaction.
- [ ] Add idempotency and stable operation references; two approvals or two requests citing one transfer cannot create duplicate credit.
- [ ] Route partial/mismatched/late transfers to reconciliation. Do not silently discard an observed transfer or create unbacked credit.
- [ ] Run recharge tests including parallel approval, transaction rollback, and stale admin version.

## Task 4.2: Withdrawal reservation and manual settlement

**Files:** Create `marketplace/payments/withdrawals.py`; `tests/test_marketplace_withdrawals.py`.

**Interfaces:** `WithdrawalService.request(...)`, `WithdrawalService.settle(...)`; guarded start/reject/cancel transitions.

**Test anchor:** `test_reserve_100_from_110_leaves_ten` asserts available 10 and reserved 100; `test_reject_releases_once` asserts available 110 and reserved zero after repeated rejection; `test_processing_timeout_does_not_release` preserves reservation and requires reconciliation.

- [ ] Write failing rule tests: balances 100→0 withdrawable, 110→100, 310→300; reject 99/101 requests and requests exceeding available-minus-ten.
- [ ] Add tests for purchased/earned/reward balance eligibility, destination ownership, concurrent spend vs reserve, duplicate request/settlement/rejection, and processing-state cancellation.
- [ ] Run withdrawal tests and confirm failures.
- [ ] Implement request transaction: lock accounts, calculate withdrawable, move AVAILABLE to RESERVED, create pending-review request and audit together.
- [ ] Implement start-processing transition with a visible operator record. Actual payout is performed manually outside SQL.
- [ ] Implement settle with a verified unique outgoing reference, RESERVED-to-payout-clearing journal transfer, status and audit in one transaction.
- [ ] Implement cancellation/rejection only before processing or after an explicitly reconciled no-transfer outcome; release the reservation once.
- [ ] Keep ambiguous external results in processing/reconciliation, with reservation intact. Never retry a bank transfer automatically after a timeout.
- [ ] Encrypt/otherwise protect stored destination details, redact logs/UI, and return only the requesting user's data.
- [ ] Run withdrawal concurrency/state-machine tests against native PostgreSQL.

## Task 4.3: User and administrator pages

**Files:** Create `marketplace/payments/routes.py`, `admin.py`, `templates/marketplace/request.html`, `templates/admin/recharges.html`, `withdrawals.html`, `reconciliation.html`; extend wallet UI; `tests/test_marketplace_payment_api.py`, `tests/test_marketplace_payment_ui.mjs`.

**Routes:** Owner request create/submit/status/cancel; admin recharge approve/reject and payout start/settle/reject. See master route contract.

**Test anchor:** `test_credit_returns_to_same_experience_without_purchase` asserts the original query/experience return path, no entitlement, and no purchase transaction until the reader explicitly unlocks.

- [ ] Write failing ACL/CSRF tests for own/other-user requests, nonadmin approval, request version conflicts, forged external status, and cross-user payout destination IDs.
- [ ] Write failing UI tests for payment instructions, pending status, rejection/reconciliation messages, exact experience return, stale price, and no automatic unlock on approval.
- [ ] Run the focused API/Node tests and confirm failures.
- [ ] Build wallet add/withdraw controls, amount validation, quote confirmation, request timeline, and clear estimates.
- [ ] Add bounded owner-only status polling/backoff and a return action to the original query/experience after credit. A changed quote requires fresh purchase confirmation.
- [ ] Build admin queues with age/status filters, verified references, reason fields, optimistic state versions, and audit links.
- [ ] Add reconciliation view comparing coin clearing totals, verified external movements, outstanding reservations, and request states. Provide audited compensating workflow, never direct balance editing.
- [ ] Smoke-test synthetic recharge approval → exact return → explicit unlock, plus reserve → reject/release and reserve → settle.
- [ ] Run the payment, wallet, and purchase suites together; check histories/ledger sums after each scenario.

## Handoff gate

- [ ] Duplicate admin requests or transfer references cannot credit/settle twice.
- [ ] Pending withdrawals cannot be spent, and release/settlement is exact once.
- [ ] All coins have the confirmed withdrawal eligibility.
- [ ] Return to the original query/answer is verified without automatic debit.
- [ ] Manual operator runbook covers mismatches, unknown payouts, and reconciliation.
