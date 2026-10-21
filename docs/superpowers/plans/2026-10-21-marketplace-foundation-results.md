# Marketplace foundation and authentication results

Date: 2026-10-21. Scope: Tasks 1.1–1.3 only, in the linked worktree
`saariv/.worktrees/marketplace-foundation`, branch `codex/marketplace-foundation-auth`.
Starting commit: `33c6553`. No changes to `app.py`, private knowledge code, or other marketplace domains.

## Delivery status

The foundation, accounts, provider adapters and login page are implemented locally.
42 marketplace tests pass with native PostgreSQL. The complete Python suite has
97 tests and the same baseline eight failures/four errors assigned to the
reliability workstream. All 23 existing Node tests pass. Fresh final review pending.

Local checkpoints:

- `f96e1bc`: database/configuration/DTO contracts, dependencies and placeholders.
- `0302ab7`: users, identities, server sessions, internal intents, owner claims, migrations and account tests.
- OAuth/final review checkpoints: recorded below after verification.

No push, PR, deployment, financial transfer, real provider login, or private-data migration was performed.
Marketplace remains opt-in (`MARKETPLACE_ENABLED=false`); the coordinator must call
`register_marketplace(app)` from the existing application after integration gates.

## Stable shared contracts

```python
from marketplace import register_marketplace  # (app) -> bool
from marketplace.db import Base, Database
from marketplace.security import current_principal, csrf_token, require_csrf, require_login, require_role
```

- `Base` subclasses SQLAlchemy `DeclarativeBase`, with shared deterministic constraint names.
- `Database(url: str)` requires `postgresql+psycopg`; it does not create tables.
- `db.engine` is the SQLAlchemy engine; `db.session_factory` is a `sessionmaker` with
  `expire_on_commit=False`. `with db.transaction() as session:` yields a `Session`,
  commits once on success, rolls everything back on error, and closes the session.
- `app.extensions["marketplace_db"]` holds this `Database`.
- Registration also exposes `marketplace_settings`, `marketplace_accounts`, and
  `marketplace_oauth` in `app.extensions`. Repeated registration is harmless.
- Registration is a no-op when disabled and never runs a migration.
- `current_principal() -> Principal` derives authority solely from the opaque server
  session. Client IDs, JSON roles, query parameters, and identity headers have no authority.
- `csrf_token() -> str` is a Jinja global; it creates a server-side guest session when
  needed. Mutations use `X-CSRF-Token` or a form `csrf_token`; `require_csrf()` also
  rejects a supplied foreign `Origin`.
- `@require_login` validates login and CSRF for unsafe methods; `@require_role("admin")`
  adds a server account role check. Future domain mutations should use these helpers.
  For guest mutations, call `require_csrf()` explicitly. No broad CORS permission is added.

`marketplace.contracts` exports the master plan's frozen dataclasses, with the exact
field names below. All DTOs have `.to_dict()`; cards and pages take keyword
`principal=Principal()` and default to the guest-safe representation.

```text
Principal(user_id: UUID | None = None, roles: frozenset[str] = frozenset())
ExperienceCard(experience_id, title, teaser, taxonomy, price_coins, author, rating, unlocked)
SearchPage(query_id, items, next_cursor, login_required, retrieval_mode)
WalletSnapshot(available_coins, reserved_coins, withdrawable_coins)
UnlockReceipt(entitlement_id, experience_id, charged_coins, available_coins)
RequestReceipt(request_id, status, coins, fiat_minor, currency, next_path)
ApprovalReceipt(experience_id, revision_id, reward_transaction_id, index_job_id)
AuthorRating(upvotes, downvotes, ranking_score)
```

`Principal.authenticated` is true only with a user UUID. `ExperienceCard.author` may
be a mapping or object with `user_id`, `display_name`, and optional `avatar_url`;
all other author fields are excluded. Guests get `author=None`, `unlocked=False`,
and no page cursor. Ratings only serialize `upvotes`, `downvotes`, `ranking_score`.
Taxonomy recursively keeps domain/subdomain/topic/subtopic names and hierarchy,
excluding experience prose and raw source fields. Services must still select only
approved identity-safe titles/teasers and enforce their own guest page cap.

`MarketplaceError(code, message, status=400, *, details=None)` produces:

```json
{"ok": false, "error": {"code": "access_denied", "message": "...", "details": {}}}
```

## Accounts and route contracts

The schema uses UUID `users.id` and these tables: `users`, `oauth_identities`,
`server_sessions`, `resume_intents`, `private_avatar_owners`, `audit_events`,
`oauth_flows`. Identity uniqueness is `(provider, subject)`. `User.email` and
identity email are optional contact information. User roles are server-managed
JSON; there is no public role-grant API. `User.is_active=False` invalidates sessions.
`AuditEvent` has `id`, `actor_id`, `action`, `target_id`, `details`, `created_at`.

`AccountService(db, *, session_ttl=86400, intent_ttl=900)` provides:

```python
identity_login(ProviderIdentity(provider, subject, email=None, display_name=None)) -> User
link_identity(*, principal: Principal, proof: ProviderIdentity) -> User
issue_session(user_id=None, *, previous_token=None) -> SessionTicket
principal(token) -> Principal
session_record(token) -> ServerSession | None
revoke_session(token) -> None
create_resume(token, *, next_path, query_id=None) -> str  # opaque one-time intent
check_resume(intent, token) -> None
consume_resume(intent, token, *, principal, query_owner_check=None) -> ResumeTarget
claim_owner(*, principal, proven_owner_id) -> None  # internal signed-cookie boundary only
```

`SessionTicket` exposes `token`, `csrf_token`, `expires_at`, hiding tokens from repr.
`ResumeTarget` exposes `next_path`, optional `query_id`. Identity proofs are internal
objects created only after provider validation; they are never accepted from browser JSON.
Concurrent identity creation/linking uses a PostgreSQL transaction advisory lock
and a unique constraint. Matching emails do not link users or wallets.

The independent `marketplace_session` cookie holds a random opaque token; only its
SHA-256 digest is stored in SQL. This preserves the separate legacy Flask signed
owner cookie. Cookies are HttpOnly, SameSite=Lax, path `/`, and Secure in production.
Successful authentication rotates both the session ID and CSRF value and revokes
the old session. The prior-session row is locked and revalidated at rotation,
including revocation while an external provider exchange was in flight.

| Route | Behavior |
| --- | --- |
| `GET /login?next=...&query_id=...` | Validated internal destination; opaque candidate query reference; shows all provider configuration states. |
| `GET /auth/login/<provider>?intent=...` | Browser-bound server intent, one-time SQL OAuth state, fixed configured callback URL. |
| `GET /auth/callback/<provider>` | Validates state/provider/browser/expiry once, verifies provider proof, consumes intent, rotates session. |
| `POST /auth/link/<provider>` | Requires authenticated session + CSRF, then a fresh provider code/proof and the same account session. |
| `POST /auth/logout` | Requires login + CSRF; revokes the server session and clears its cookie. |
| `POST /auth/claim-owner` | Requires login + CSRF and an empty JSON object; validates the original signed Flask cookie and claims its `knowledge_owner` once. |

No route accepts an owner/profile ID to claim private data. Claims record a link,
without copying or publishing private sources.

Allowed `next` values are `/`, `/experiences/new`, `/wallet`,
`/experiences/<UUID>`, `/experiences/<UUID>/edit`, `/wallet/requests/<UUID>`.
Embedded queries/fragments, encoded separators, backslashes, login loops and external
URLs are rejected. Query references must match `[A-Za-z0-9_-]{8,128}`; no story/query
body goes in OAuth URLs. Only OAuth state, nonce, public client metadata and Google
PKCE challenge are sent to providers.

**Search integration hook:** set
`app.config["MARKETPLACE_QUERY_OWNER_CHECK"]` to a callable taking keyword arguments
`principal: Principal`, `query_id: str`, `session_digest: str`, returning a boolean.
It must verify that the opaque query belongs to that account or the original guest
session (and may bind the guest query to the account). It must not perform a money
mutation. Without a hook, or if it returns false, the selected internal experience
still resumes but the unverified query ID is excluded. A query ID is never treated
as proof of ownership. A successful hook restores `?query_id=<opaque-id>`.

## OAuth sources and operational gates

Authlib 1.9.1's actual HTTP/JWT implementation is exercised by synthetic transport
fixtures and locally generated RSA signatures. State/nonce/verifier are stored in
PostgreSQL, rather than Authlib's normal Flask signed-cookie state storage.
Google/LinkedIn use pinned official discovery URLs, RS256, nonce, signature,
issuer/audience/time validation and provider-subject mapping. Google uses S256 PKCE;
both documented Google issuer forms are accepted. LinkedIn missing email works.
Tokens are used only during callback and never persisted.

Sources checked on 2026-10-21:

- [Authlib Flask integration](https://docs.authlib.org/en/latest/oauth2/client/web/flask.html).
- [Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect) and
  [discovery](https://accounts.google.com/.well-known/openid-configuration).
- [LinkedIn OIDC](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2) and
  [discovery](https://www.linkedin.com/oauth/.well-known/openid-configuration).
- Meta [manual login flow](https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/)
  and [Graph versions](https://developers.facebook.com/docs/graph-api/changelog/versions/)
  returned HTTP 429/inaccessible. Current live version certification is unavailable.

Facebook's adapter uses the versioned authorization-code flow, app token inspection,
matching app/user IDs, token/data-access expiry and `appsecret_proof` for `me`.
`FACEBOOK_GRAPH_VERSION` has **no default**: operators must verify a currently supported
version and configure it explicitly. The synthetic tests' `v26.0` is not a live
version certification. The unconfigured page gives no fake login shortcuts.

All three registered provider applications, approved redirect URLs, production
secrets/HTTPS, and supported system-browser acceptance (success, denial, return
navigation) remain launch gates. No real client credentials were requested or read.

## Verification evidence

Runtime: `/Users/asali/Documents/New project 3/saariv/.venv-rag/bin/python`.
New pinned dependencies were installed **only** into this worktree's ignored
`.local-dev/deps`; the shared virtualenv was not modified. Prefix Python commands
with `PYTHONPATH=.local-dev/deps` here, or install the committed requirements in
the integration environment. Local TCP test commands require sandbox escalation.

Test database: `postgresql+psycopg://saariv_dev@127.0.0.1:55432/saariv_marketplace_test`.
Tests explicitly require `TEST_DATABASE_URL`, reject non-test databases and the
configured application database, and create/drop random `test_mpf_*` schemas only.
There is no SQLite substitute or missing-configuration skip.

```sh
TEST_DATABASE_URL=postgresql+psycopg://saariv_dev@127.0.0.1:55432/saariv_marketplace_test \
PYTHONPATH=.local-dev/deps \
'/Users/asali/Documents/New project 3/saariv/.venv-rag/bin/python' \
  -m unittest discover -s tests -p 'test_marketplace_*.py' -v
```

Result: **42 tests passed**. Includes native transaction rollback and migration
`base → 001_accounts_sessions → base → 001_accounts_sessions` in an empty disposable
PostgreSQL schema. Migration 001 includes OAuth flows in its final initial schema;
use its final version when applying this unintegrated work. Do not assume the earlier
intermediate account commit's 001 is the final schema.

The complete existing suite was run with `dotenv.load_dotenv` replaced only in the
test process to prevent parent `.env` discovery. All app/provider configuration is
synthetic, and no production profiles or provider keys were read:

```sh
TEST_DATABASE_URL=postgresql+psycopg://saariv_dev@127.0.0.1:55432/saariv_marketplace_test \
FLASK_SECRET_KEY=synthetic-full-suite-signing-key-123456789 \
EMBEDDING_PROVIDER=none CHAT_PROVIDER=extractive PYTHONPATH=.local-dev/deps \
'/Users/asali/Documents/New project 3/saariv/.venv-rag/bin/python' -c \
'import dotenv, unittest; dotenv.load_dotenv=lambda *args, **kwargs: False; suite=unittest.defaultTestLoader.discover("tests"); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())'
```

Result: **97 tests; 8 failures + 4 errors**, all existing reliability failures:

- `test_experience_story.ExperienceStoryTests.test_empty_story_or_headings_without_narrative_are_rejected`: three failing story subcases.
- `test_knowledge_api.KnowledgeAPITests.test_extract_mode_preserves_asked_wording_and_returns_citations`.
- `test_knowledge_api.KnowledgeAPITests.test_failed_first_import_retries_using_the_signed_browser_cookie`.
- `test_knowledge_service.KnowledgeServiceTests.test_equal_dimensions_do_not_allow_mixing_model_profiles`.
- `test_knowledge_service.KnowledgeServiceTests.test_failed_import_preserves_previous_source_and_vectors`.
- `test_knowledge_service.KnowledgeServiceTests.test_failed_rebuild_does_not_publish_a_partial_profile`.
- Error: `test_knowledge_answers.AnswerTests.test_compatible_chat_uses_configured_model_and_grounding_instructions`.
- Error: `test_knowledge_providers.ProviderTests.test_cohere_uses_distinct_query_and_document_roles`.
- Error: `test_knowledge_providers.ProviderTests.test_compatible_adapter_orders_response_vectors_and_records_usage`.
- Error: `test_knowledge_providers.ProviderTests.test_ollama_native_adapter_and_prefixes`.

`/opt/homebrew/bin/node --test tests/*.mjs`: **23 passed, zero failed/skipped**.
`PYTHONPATH=.local-dev/deps <python> -m compileall -q marketplace migrations tests/test_marketplace_foundation.py tests/test_marketplace_accounts.py tests/test_marketplace_oauth.py`: passed.
`git -c core.fsmonitor=false diff --check`: passed.

Local detailed logs are in ignored `.local-dev/`: `accounts-test.log`,
`oauth-red.log`, `oauth-green.log`, `full-suite-accounts.log`,
`full-suite-oauth.log`, `node-tests.log`.

## Rulings and remaining work

1. Retained the supplied worktree and left `app.py` integration to the coordinator,
   as directly delegated. Cost: coordinator must register the completed package.
2. Used an independent marketplace cookie while preserving the signed legacy cookie.
   Cost: two browser cookies; avoids changing existing private owner behavior.
3. Unverified query IDs remain server candidates and are excluded from navigation
   until the domain hook approves ownership. Cost: query restoration awaits integration;
   selected experience/editor restoration already works.
4. Facebook has no implicit Graph version. Cost: it remains unavailable until
   an operator verifies/configures a supported version.

No financial-domain implementation or baseline defect repair was attempted.
