# Local mock marketplace walkthrough

Open [Saariv](http://127.0.0.1:8080/). The beige **Saariv demo** banner confirms mock mode.
Use its **Reader**, **Author**, and **Admin** buttons to switch accounts in one browser.

This is a local prototype with synthetic stories and simulated coins. Mock Google,
LinkedIn, and Facebook do not contact those companies. Search uses local keyword
matching, followed by author rating; it does not call GPT or an embedding API.
Browser dictation is still available and may use the browser's remote speech service.
The browser checks below used typed input, with no microphone recording.

## Personas

| Button | Demo account | Use it for |
| --- | --- | --- |
| Reader | Alex Reader | Search, recharge, unlock, vote, withdraw |
| Author | Maya Author | Write, submit, receive sales and publication rewards |
| Admin | Demo Admin | Review stories, approve recharges, settle withdrawals |

All three mock provider choices sign into the selected persona. They rotate the
browser session and preserve the selected experience and owning guest query.
**Sign out of demo** returns to the guest view. Data and balances survive restarts.

## 1. Discover, sign in, and read

1. Sign out if needed. Search **How did people find housing before moving to a new city?**
2. Guests see at most **four** cards. Actual author identities and full stories are omitted.
3. Open **Finding housing before a city move**, priced at **25 coins**.
4. Choose **Continue with mock Google**, keeping **Reader** selected. LinkedIn and
   Facebook are equivalent mock choices. You return to the exact selected story.
5. The title, public introduction, author, and price are visible. The full body stays locked.
6. Choose **Unlock for 25 coins**. If the wallet is short, the app opens the wallet
   with the experience and query saved. Follow the recharge steps below.
7. Confirm **Unlock** after funding. The reader pays 25 coins and Maya receives 25.
8. The exact story appears. Choose **Helpful**, **Not helpful**, or **Remove vote**.
   The vote contributes to that author's rating and subsequent search ordering.
9. Reopen or refresh: access is permanent for this demo account, with no second charge.

On a fresh demo database, Reader starts at zero coins. The sample story may already
be unlocked after a previous walkthrough; choose another card to test a new purchase.

## 2. Recharge and return to the selected story

1. As Reader, open **Wallet**, or arrive there from an insufficient balance.
2. Leave **Demo coins to add** at **200** and choose **Create demo recharge**.
3. The request shows **Pending payment**, the demo user ID, and a simulated memo.
   **Do not send money**: no bank transfer or real account is configured.
4. Choose **Simulate transfer**. The request becomes **Pending review**; balance is unchanged.
5. Switch to **Admin**, open **Demo admin**, and choose **Approve demo recharge**.
6. Switch back to **Reader** → **Wallet** → the recharge's **View request** link.
7. Status is **Credited**. If the recharge began from a locked story, choose
   **Return to your experience** to restore that story and its query.
8. Confirm **Unlock** separately. Approving a recharge never auto-purchases a story.

The demonstration conversion is **$1 = 100 coins**. Approval can be replayed without
crediting twice. The admin acts immediately in this local walkthrough; there is no
real bank verification, hour-long credit job, or payment provider integration.

## 3. Write, review, publish, and earn

1. Switch to **Author** and choose **＋ Share an experience**.
2. Type or paste a story. Dictation can fill the same story box if supported by your browser.
3. Add a **Title**, **Public teaser**, comma-separated **Taxonomy topics**, and
   a positive whole-number **One-time price** such as **20**.
4. Choose **Save draft**. It remains private and gives no reward.
5. Choose **Submit for review**. The revision becomes read-only and still gives no reward.
6. Switch to **Admin** → **Demo admin**. Expand **Read the exact submitted story**.
7. Choose **Approve publication**. Approval publishes it and transfers **10 demo coins**
   from the seeded reward treasury to its author, once.
8. Switch to **Author** → **My experiences**. The approved story links to its full detail.
9. Check **Wallet** for the publication reward. Search a distinctive word from the
   new title as Reader to find the new card; its body still requires an unlock.

Exact duplicate stories by the same author, after case/whitespace normalization,
cannot earn another approval reward. Replayed approval also gives no new reward.
This check does not implement semantic plagiarism or production abuse review.
Declined revisions remain read-only; an author can start another draft.

## 4. Withdraw and track status

1. As Reader or Author, open **Wallet**.
2. Request at least **100 coins**, in multiples of **100**, leaving at least **10 available**.
   Purchased and earned coins both qualify.
3. Submission immediately moves those coins from available to reserved. They cannot be spent.
4. Switch to **Admin** → **Demo admin** → **Start demo payout**. Status becomes **Processing**.
5. Choose **Settle simulated payout**. Status becomes **Settled**, consuming the reservation.
6. Switch to the owner → **Wallet** → **View request** to inspect status and history.

Before processing starts, the owner can cancel or Admin can reject, releasing the
reservation once. Processing requests must be settled; no actual payout occurs.
There is no real one-day settlement scheduler in mock mode.

## Browser acceptance observed on 2026-10-22

The in-app browser completed all four flows above, including saving and submitting
**My weekend housing checklist**, approval, a rating vote, and a settled withdrawal.

| Event | Reader available | Reader reserved | Author available |
| --- | ---: | ---: | ---: |
| Fresh seed | 0 | 0 | 0 |
| Recharge approved | 200 | 0 | 0 |
| Unlock sample for 25 | 175 | 0 | 25 |
| Refresh unlocked story | 175 | 0 | 25 |
| New publication approved | 175 | 0 | 35 |
| Withdraw 100 requested | 75 | 100 | 35 |
| Simulated payout settled | 75 | 0 | 35 |

These synthetic records remain in the demo for inspection. Repeating a walkthrough
adds to the current state. Recharge from Wallet to add more demo coins.

## Run again, natively

Requirements: Python 3.11+, `requirements.txt`, and a running local PostgreSQL role
with permission to create the dedicated demo database. No containers are used.

From this worktree, using the existing shared Python environment:

```sh
cd '/Users/asali/Documents/New project 3/saariv/.worktrees/marketplace-mock'
'/Users/asali/Documents/New project 3/saariv/.venv-rag/bin/python' run_mock.py
```

`run_mock.py` creates `saariv_marketplace_mock` on `127.0.0.1:55432` if absent,
initializes synthetic data idempotently, and serves `127.0.0.1:8080`.
It does not reset previous demo transactions. For a fresh database, choose a new
dedicated name ending in `_mock` with `--database-url`; choose another port with
`--port`. `--init-only` seeds without starting the server.

The launcher disables dotenv discovery, clears inherited provider/mail credentials,
forces keyword/extractive mode, and uses a separate ignored signing secret and
knowledge directory. Manual configuration requires `MARKETPLACE_ENABLED=true`,
`MARKETPLACE_MOCK_MODE=true`, a development/test environment, and a loopback origin
and dedicated local `_mock` or `_test` database. Connection overrides are rejected.
Mock requests also require loopback Host/IP, CSRF, and matching Origin for writes.

Real OAuth and legacy provider-calling routes are unavailable while mock mode is
active. With mock mode off, existing adapters and the private import flow retain
their original behavior. This code uses separate `demo_*` tables and explicit
initialization, without changing the real account migration metadata.

## Verification and production boundary

Final automated checks: **132 Python tests**, **54 JavaScript tests**, Python
compilation, and `git diff --check` passed. PostgreSQL tests use disposable schemas
in `saariv_marketplace_test`. They cover access boundaries, all three mock providers,
query restoration, concurrent unlocks, duplicate publication approval, recharge
replay, and withdrawal reservation/release/settlement.

Logs and browser evidence:

- `/private/tmp/saariv-mock-python-final-20261022.log`
- `/private/tmp/saariv-mock-node-final-20261022.log`
- `/private/tmp/saariv-mock-wallet-20261022.png`

This remains a simulated marketplace. Its wallet cache and per-account history are
demo bookkeeping, not a production financial ledger. Real OAuth app registration,
verified payments, payout operations, production migrations/accounting, and public
semantic retrieval still require the [remaining marketplace phases](superpowers/plans/2026-10-21-experience-marketplace.md).
