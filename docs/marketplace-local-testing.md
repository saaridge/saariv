# Local marketplace run and testing

## Current build

The RAG reliability, account/authentication foundation and reader/writer screens
have been integrated on `codex/experience-marketplace`. The new homepage and login
are mounted in the real Flask app. `/try` retains the private import/playground flow.

The full marketplace is not implemented yet. Public search, persistent authoring,
paid access, wallet, recharge/withdrawal, publication rewards and ratings need their
remaining roadmap phases. Pending operations return HTTP 503 with
`feature_unavailable`; they do not simulate results or money. All three social
provider applications need configuration before a real login can complete.

## Running natively

The local PostgreSQL 16.11 cluster is already running on `127.0.0.1:55432`.
`saariv_marketplace_dev` is the application database; `saariv_marketplace_test`
is reserved for disposable test schemas. Account/session migration 001 is applied
to the development database.

From the repository root, the running web process uses:

```sh
MARKETPLACE_ENABLED=true \
MARKETPLACE_PUBLIC_BASE_URL=http://127.0.0.1:8080 \
DATABASE_URL=postgresql+psycopg://saariv_dev@127.0.0.1:55432/saariv_marketplace_dev \
.venv-rag/bin/python -m flask --app app run \
  --host 127.0.0.1 --port 8080 --no-debugger --no-reload
```

The existing private embedding/chat environment is preserved. No API key is
copied into these commands. Setting `MARKETPLACE_ENABLED=false` keeps the original
marketing homepage. No Docker is used.

## Fresh automated evidence — 2026-10-21

```sh
TEST_DATABASE_URL=postgresql+psycopg://saariv_dev@127.0.0.1:55432/saariv_marketplace_test \
FLASK_SECRET_KEY=synthetic-integration-test-signing-key-20261021 \
EMBEDDING_PROVIDER=none CHAT_PROVIDER=extractive \
.venv-rag/bin/python -c 'import dotenv, unittest; dotenv.load_dotenv=lambda *a, **k: False; result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover("tests")); raise SystemExit(not result.wasSuccessful())'

/opt/homebrew/bin/node --test tests/*.mjs
.venv-rag/bin/python -m compileall -q app.py knowledge marketplace
git -c core.fsmonitor=false diff --check
```

Results: **114 Python tests passed**, **53 JavaScript tests passed**, compilation
and whitespace checks passed. The Python run disables dotenv discovery and uses
synthetic provider fixtures, plus real native PostgreSQL with disposable schemas.
The app-entry-point tests cover mounting, guest login return, private editor,
legacy `/try`, and honest unavailable-feature errors. A first-person excerpt
regression was observed failing before the frontend fix and passing afterward.

Local logs:

- `/private/tmp/saariv-integrated-python-final-20261021.log`
- `/private/tmp/saariv-integrated-node-final-20261021.log`
- `/private/tmp/saariv-runtime-red-20261021.log`
- `/private/tmp/saariv-runtime-green-20261021.log`
- `/private/tmp/saariv-citation-red-20261021.log`

## Live checks

| Check | Observed result |
| --- | --- |
| `/health` | HTTP 200. |
| New homepage and assets | Loaded in the in-app browser with query box and dictation control. |
| Typed public query | Visible unavailable message; backend is not implemented. This is a pending acceptance case. |
| Guest Add experience | Redirected to login with the original editor destination. |
| Social providers | Google, LinkedIn, Facebook show Not configured; live sign-in not verified. |
| `/try` | Existing profile/onboarding screen loaded. |
| Synthetic private story | Imported using the configured embedding API; one indexed chunk, hybrid mode. |
| Private retrieval | HTTP 200, hybrid mode, one matching hit. |
| Another browser session | HTTP 401 when attempting to select the synthetic owner's data. |
| Playground answer | HTTP 200, extractive mode, one citation. No live GPT generation is claimed. |
| Cleanup | Owning session deleted only the synthetic story, HTTP 200. |

No real microphone recording, social-provider login, coin transfer, payment, or
withdrawal was performed. Browser proof: `/private/tmp/saariv-running-20261021.png`.

See the [implementation roadmap](superpowers/plans/2026-10-21-experience-marketplace.md)
for the remaining delivery and release gates.
