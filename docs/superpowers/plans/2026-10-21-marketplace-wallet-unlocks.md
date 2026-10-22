# Marketplace Wallet and Permanent Unlock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this subsystem task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a balanced coin ledger and atomic one-time experience purchases with permanent entitlements.

**Architecture:** PostgreSQL owns append-only journal entries, locked account projections, current quotes, and unique reader/experience entitlements. Financial and access changes commit together.

**Tech Stack:** PostgreSQL, SQLAlchemy 2, psycopg 3, Flask, unittest with real native PostgreSQL concurrency.

**Spec:** [Marketplace design](../specs/2026-10-21-experience-marketplace-design.md)

**Roadmap:** [Master plan](2026-10-21-experience-marketplace.md)

**Prerequisite:** Accounts and experience/revision schema from Phases 1–2.

## Global Constraints

- Pay once; reopen without charge. Authors read their own stories without paying.
- Purchased, earned, and publication reward coins share withdrawable eligibility.
- Integer coins only; no negative user/treasury accounts.
- No network calls inside locked money transactions.
- SQLite-only tests cannot satisfy this phase.
- No live paid listings until the complete funded approval and operations gate in Phase 5.

## Review Focus

Atomic entitlement + transfer, duplicate request keys and alternate keys, concurrent overspend, stale prices, self-purchase, and unauthorized content access.

## Task 3.1: Account and immutable ledger schema

**Files:** Create `marketplace/wallet/models.py`, `ledger.py`; migration `003_wallet_entitlements.py`; `tests/test_marketplace_ledger.py`.

**Interface:** `LedgerService.post_transfer(session, kind, debit_account_id, credit_account_id, coins, idempotency_key, metadata)`. It participates in the caller transaction and does not commit itself.

**Test anchor:** `test_transfer_20_is_balanced` starts reader at 100 and author at zero, then asserts balances 80/20, two entries summing to zero, and one transaction; `test_concurrent_debits_cannot_make_balance_negative` asserts at most one competing 80-coin debit succeeds from a 100-coin balance.

- [ ] Write failing tests for balanced signed entries, zero/negative/noninteger amounts, immutable history, unique operation references, payload mismatch under replay, rollback, and forbidden negative accounts.
- [ ] Add parallel debit tests against actual PostgreSQL connections, with two operations competing for one limited balance.
- [ ] Run `python -m unittest discover -s tests -p 'test_marketplace_ledger.py' -v`; confirm missing implementation fails rather than skipping for absent database configuration.
- [ ] Implement user AVAILABLE/RESERVED accounts, platform clearing accounts, nonnegative reward treasury, transaction header/entries, balance projection, and scoped idempotency records.
- [ ] Lock accounts in stable order, validate available funds, write entries/projections, and enforce sum-zero journal integrity with deferred database validation.
- [ ] Protect posted journal records from updates/deletes. Corrections are new compensating operations with references and reasons.
- [ ] Implement reconciliation queries for entry sums and account projections; fail health/admin reconciliation if they differ.
- [ ] Run ledger tests including transaction rollback after each domain failure point. Inspect the migration's constraints and role permissions.

## Task 3.2: Quotes, transfers, and permanent entitlements

**Files:** Create `marketplace/wallet/purchases.py`; extend wallet schema with quotes/entitlements; `tests/test_marketplace_unlocks.py`.

**Interface:** `UnlockService.unlock(user_id, experience_id, quote_id, idempotency_key) -> UnlockReceipt`.

**Test anchor:** `test_parallel_unlocks_create_one_entitlement_and_debit` starts reader at 100, price 20, issues parallel unlocks, and asserts reader 80, author 20, one entitlement, and one purchase transaction even with different request keys.

- [ ] Write failing tests for successful transfer, permanent revisit, same/different-key duplicate purchases, insufficient coins, stale quote, quote belonging to another reader, archived experience, and self-purchase.
- [ ] Add a parallel same-experience test (many simultaneous requests, exactly one transfer/entitlement) and distinct-experience race (no negative balance).
- [ ] Run unlock tests and confirm failures.
- [ ] Create server quotes from the current approved revision/price, with bound reader/experience and expiry. A stale revision or changed price requires a new quote.
- [ ] Implement the domain transaction: validate current listing/quote, check existing entitlement, lock accounts, debit reader/credit author, create entitlement/receipt/audit, commit once.
- [ ] Enforce unique(reader_id, experience_id) and a stable purchase operation reference independently of the supplied HTTP key. Handle uniqueness races by returning the existing entitlement after rollback.
- [ ] Make same-key replays return their stored result; reject key reuse with changed payload. A new request for an already-owned experience returns zero additional charge.
- [ ] Retain the purchased revision reference and normal access to later approved revisions. Archiving prevents new sales without deleting entitlements/history.
- [ ] Run unlock and ledger tests on PostgreSQL.

## Task 3.3: Protected content and wallet pages

**Files:** Create `marketplace/wallet/routes.py`, `templates/marketplace/wallet.html`, `static/js/wallet.js`; extend experience routes/templates and search card entitlement lookup; `tests/test_marketplace_wallet_api.py`, `tests/test_marketplace_purchase_ui.mjs`.

**Routes:** Wallet/balance/history, experience quote/unlock POSTs, authorized content GET. Purchases use principal identity, CSRF, and server prices.

**Test anchor:** `test_locked_content_get_has_no_story_text` asserts access denied and zero body/source fields; `test_owned_content_get_never_debits` repeats a successful content GET and asserts the transaction count is unchanged.

- [ ] Write failing API tests for guest denial, user ID/price spoofing, wallet history isolation, guessed content IDs, old knowledge endpoint bypass, CSRF, and lock status.
- [ ] Write failing controller tests for explicit confirmation, double-click, stale quote refresh, insufficient-funds return intent, replay receipt, and owned-card navigation.
- [ ] Run the API and Node tests and confirm failures.
- [ ] Add content authorization for author, permitted admin, or permanent entitlement. Locked preview HTML/JSON must not include full body/source snippets.
- [ ] Return available/reserved/withdrawable balances from SQL; calculate withdrawable using the confirmed rule, even before payout APIs exist.
- [ ] Integrate price/confirmation UI and receipts. Disable repeated clicks while pending, while retaining server idempotency as the actual protection.
- [ ] Store original query/selected experience on insufficient funds; route to the Phase 4 recharge page. No debit occurs on GET/login/status poll.
- [ ] Mark already owned cards and remove their purchase action; render exact story with its approved provenance after access checks.
- [ ] Run API/Node tests and a synthetic transfer/refresh/reopen smoke scenario.

## Handoff gate

- [ ] Ledger invariants hold on PostgreSQL, including concurrent requests.
- [ ] One unlock yields one debit and one permanent entitlement.
- [ ] No unauthorized content or other-user wallet history is returned.
- [ ] Quote/price changes never charge silently.
- [ ] Available/reserved balances and the recharge resume contract are ready for Phase 4.
