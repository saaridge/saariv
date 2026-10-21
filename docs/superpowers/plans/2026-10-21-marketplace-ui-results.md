# Marketplace UI results — 2026-10-21

Scoped implementation of Task 2.4 in [the publishing/search plan](2026-10-21-marketplace-publishing-search.md), using [the marketplace design](../specs/2026-10-21-experience-marketplace-design.md).

Worktree: `/Users/asali/Documents/New project 3/saariv/.worktrees/marketplace-ui`

Branch: `codex/marketplace-reader-writer-ui`

Starting commit: `33c6553`

Implementation commit: `7d5348c` (`feat(ui): add marketplace reader and private draft screens`)

## Delivered scope

- Responsive white/slate homepage with editable typed/dictated query, explicit search, safe cards, truthful retrieval-mode label, empty/error states, pagination, login/wallet header, and plus action.
- Guest cards contain a blurred **generic** “Community author” placeholder. Guest rendering and retained controller state discard author objects, body/source fields, and usable cursors; the UI also caps a guest page at four. The server must enforce the same limits independently.
- Guest card/more URLs carry only an internal `next` path and opaque `query_id`. Every plus link targets `/experiences/new` for the server authentication guard. Raw query text stays out of login/OAuth URLs.
- Private author editor with paste/type/dictation, exact narrative preview, public card preview, title/teaser/taxonomy, positive integer coin price, save and explicit review submission, optimistic version conflict handling, and unsaved-edit navigation protection.
- Separate server-rendered locked and authorized experience states. Locked pages omit story/source data, even if it is accidentally supplied in render context. The purchase control is explicitly disabled pending backend integration; no load/navigation/search/login action calls quote/unlock APIs.
- Shared existing `StoryDictation` is reused without modification. Capture starts only after a click. Stop waits for final words; saving/searching then requires an explicit reviewed action. Cancel, visibility changes, navigation, permission failures, and unsupported recognition preserve the visible text.
- All browser writes use same-origin credentials and `X-CSRF-Token` from the `csrf_token()` meta tag. User content uses Jinja autoescaping, `tojson`, and DOM `textContent`. No financial state is held in `localStorage`.

Only the seven assigned frontend/test files and this report changed. `app.py`, dependency files, marketplace Python/domain code, login template, existing dictation/main/style files, and existing tests were not edited.

## Integration status

**This branch does not connect runtime routes.** The application still serves its existing homepage until the backend integration workstream mounts these templates behind the marketplace feature flag. The Flask rendering tests use isolated fixture applications; browser API responses are deterministic synthetic fixtures. They do not establish real search, draft persistence, authentication, entitlements, money movement, approval, or reward behavior.

The complete marketplace release remains gated by the other workstreams. Native PostgreSQL at `127.0.0.1:55432` accepted the readiness check using the explicitly named `saariv_marketplace_test` connection target. This UI scope adds no SQL tests and claims no financial/concurrency gate.

## Required Jinja context

Render plain JSON-compatible DTO mappings (UUIDs serialized to strings), with normal HTML autoescaping enabled. Do not pass ORM records or unrestricted source/profile objects.

All three templates require:

| Name | Contract |
| --- | --- |
| `principal` | Server-built principal with `user_id: string \| null`; an object or mapping is supported. Never derive this from a request body/query. |
| `wallet` | `WalletSnapshot` mapping or `null`. The header displays only supplied `available_coins`; null shows “Wallet”, rather than an invented zero balance. |
| `csrf_token()` | Registered callable returning the active session's CSRF token. |
| `url_for()` | Standard Flask helper for local static assets. |

`home.html` additionally requires:

| Name | Contract |
| --- | --- |
| `initial_query` | Editable string, normally empty or restored server-side from an authorized query session. |
| `search_page` | `null`, or the `SearchPage` below. Initial cards are rendered on the server and hydrated from an allowlisted JSON projection. |

`editor.html` additionally requires `draft: null | DraftDTO`. The route must verify author ownership before supplying a draft. As defense in depth, a guest render omits all draft fields/JSON and shows the login return link. Existing submitted/approved/rejected revisions render read-only; editing later immutable revisions requires the backend to supply a new editable draft. The UI does not invent a clone/revision endpoint.

`experience.html` additionally requires:

| Name | Contract |
| --- | --- |
| `experience` | Safe `ExperienceCard`, never a full experience/revision record. |
| `query_id` | Opaque string or null, for an internal return to the original query. |
| `access_state` | `locked`, `author`, `admin`, or `unlocked`, decided by the server after ownership/role/entitlement checks. Unknown values fail closed. |
| `content` | `null` when locked; otherwise `{body: string}` containing only the exact authorized narrative. No generated replacement. |

Only a signed in principal with `author`, `admin`, or `unlocked` access and non-null content renders the narrative. Backend GET/API authorization and private/no-store response policy remain mandatory; a template condition is not an authorization service.

## Consumed HTTP contracts

### Search

`POST /api/search`, JSON `{ "query": "edited question" }`; pagination adds `"cursor": "opaque-cursor"` and retains the last successfully submitted query, even if the text box has since been edited.

```json
{
  "query_id": "opaque-query-id",
  "items": [{
    "experience_id": "experience-uuid",
    "title": "Approved public title",
    "teaser": "Approved public teaser",
    "taxonomy": ["Relocation", "Housing"],
    "price_coins": 25,
    "author": null,
    "rating": {"upvotes": 0, "downvotes": 0, "ranking_score": 0.5},
    "unlocked": false
  }],
  "next_cursor": null,
  "login_required": true,
  "retrieval_mode": "hybrid"
}
```

For authenticated cards, `author` is null or `{ "display_name": "Approved display name" }`. The UI retains/displays only that name; no avatar, profile URL, or author ID is required. Taxonomy is an ordered list of display strings; flatten any richer domain taxonomy in the server DTO adapter without changing its meaning. Prices and vote counts are nonnegative safe integers (price strictly positive).

The UI displays `hybrid` as “Semantic + keyword search”, `dense` as “Semantic search”, and `lexical` / `lexical_fallback` as “Keyword search”. Unknown modes show “Search mode unavailable”. It does not claim hybrid success for lexical fallback. It does not rerank results. Actual helpful percentages use real vote counts; zero votes show “New author”, rather than treating the Bayesian prior as reviews.

Guests require null author, at most four cards, and no next cursor **on the server**. Public title/teaser identity safety remains a moderation responsibility. Cards are never expanded into invented stories or source snippets.

### Private draft APIs

The plan defines routes and version checking but not JSON member names. The following is the concrete UI adapter contract for backend integration:

```json
{
  "draft_id": "draft-uuid",
  "version": 3,
  "status": "draft",
  "title": "Public title",
  "teaser": "Public teaser",
  "taxonomy": ["Relocation", "Housing"],
  "price_coins": 25,
  "body": "I asked about leases. I planned a move. I had not moved yet."
}
```

| Request | JSON body | Successful response consumed by UI |
| --- | --- | --- |
| `POST /api/experiences/drafts` | `title`, `teaser`, `taxonomy`, `price_coins`, `body`; no client owner/status | `{draft_id, version, status: "draft"}`, HTTP 200/201 |
| `PATCH /api/experiences/drafts/<draft_id>` | Same fields plus current positive integer `version` | `{draft_id, version, status: "draft"}` |
| `POST /api/experiences/drafts/<draft_id>/submit` | `{version}` from the preceding successful save | `{draft_id, version, status: "submitted"}` |

Saving permits incomplete public metadata but requires a story and a positive whole-number price. Submission additionally requires title, teaser, and at least one taxonomy topic. The server must apply its own full narrative/taxonomy/size/ownership validation and may return field-specific messages. Body text is transmitted unchanged; taxonomy input is split on commas, trimmed, and deduplicated without inference or GPT calls. No client author ID, approval flag, reward flag, balance, or entitlement is submitted.

The editor saves first on explicit submit, then submits the returned version. If the author changes fields while the save is in flight, it preserves those edits and requires another reviewed submit; it does not submit the stale saved snapshot automatically. Once the submit request is in flight, all draft fields become read-only so displayed text remains the submitted revision. Duplicate clicks while a request is pending produce no additional writes.

HTTP 409 preserves edits, shows an explicit copy-before-reload instruction, and blocks blind retries. It does not adopt a newer server version and overwrite it. The backend must provide an owner-authorized way to resume the saved draft when rendering the editor; this branch does not invent a new GET route. Creation retry idempotency and durable cross-reload draft selection belong in that adapter.

### Errors and login returns

Non-2xx JSON errors use `{ "error": { "code": "version_conflict", "message": "A newer draft exists." } }`. All HTTP 409 draft writes enter conflict handling. HTTP 401 preserves the text and instructs signing in again before retrying. Network failures and malformed responses restore usable controls and retain the visible query/draft. Error strings render as inert text, never HTML; no raw non-JSON error page is inserted into the DOM.

The `/login` handler must validate `next`, resolve the opaque `query_id`, and create its own session-bound resume intent. A selected card uses `/login?next=%2Fexperiences%2F<id>&query_id=<opaque-id>`; guest “more” uses `next=%2F`. Plus routes directly to `/experiences/new`, whose guard must preserve the destination. No successful login or return causes a purchase. Real provider URLs and account/session mechanics remain in the authentication workstream.

## Verification evidence

All commands ran in the assigned worktree. The shared Python runtime is `/Users/asali/Documents/New project 3/saariv/.venv-rag/bin/python`; Node is `/opt/homebrew/bin/node`.

| Check | Actual result |
| --- | --- |
| Initial new UI tests | 25 failed for missing controllers/templates, before implementation. |
| Initialization regression | Search button remained disabled in the fixture; observed failure, then fixed. |
| Submission race regression | Text remained editable during review POST; observed failure, then fixed. |
| `node --test tests/test_marketplace_ui.mjs` | **29 passed**, zero failures/skips. Includes isolated Flask/Jinja rendering and final review status regressions. |
| `node --test tests/*.mjs` | **52 passed**, zero failures/skips; the existing 23 dictation/import tests remain unchanged. |
| Full Python unittest discovery | **55 tests, 8 failures, 4 errors**, matching the unrelated starting baseline; names listed below. |
| `python -m compileall -q app.py knowledge` | Passed. |
| `node --check static/js/marketplace.js` and `node --check static/js/authoring.js` | Passed. |
| `git -c core.fsmonitor=false diff --check` | Passed. |
| Native PostgreSQL readiness | Explicit `saariv_marketplace_test` target on port 55432: accepting connections. No SQL data changes or financial tests in this scope. |

The full Python suite was invoked with `.env` loading disabled before application imports, so deterministic test setup does not depend on developer secrets:

```sh
'/Users/asali/Documents/New project 3/saariv/.venv-rag/bin/python' \
  -c 'import dotenv, runpy; dotenv.load_dotenv = lambda *a, **k: False; runpy.run_module("unittest", run_name="__main__")' \
  discover -s tests -v
```

Fresh headless Chrome with an isolated temporary profile checked guest/reader/empty homepage, editor, locked detail, and authorized detail at **1440×1050** and **390×844**. No horizontal overflow or browser script errors occurred. Keyboard Tab reached the skip link and brand. Desktop/mobile screenshots were inspected, including guest card regions and the editor. Real microphone APIs were disabled for layout inspection; a separate deterministic recognition class tested actual DOM bindings. That second browser pass verified edited dictation, one search on double-click, the CSRF header, guest resume URL, plus navigation, versioned save/submit, immutable submitted fields, and zero quote/unlock calls. Its requests were intercepted against a synthetic `.test` origin; it made no real provider or payment calls. Browser QA required sandbox escalation to launch a fresh browser. A local Flask listening socket was blocked in the sandbox, so rendered local fixtures and intercepted browser requests were used instead.

Python baseline failures, unchanged:

- `test_experience_story.ExperienceStoryTests.test_empty_story_or_headings_without_narrative_are_rejected` — three failing subtests: empty string, whitespace, headings without paragraphs.
- `test_knowledge_api.KnowledgeAPITests.test_extract_mode_preserves_asked_wording_and_returns_citations`.
- `test_knowledge_api.KnowledgeAPITests.test_failed_first_import_retries_using_the_signed_browser_cookie`.
- `test_knowledge_service.KnowledgeServiceTests.test_equal_dimensions_do_not_allow_mixing_model_profiles`.
- `test_knowledge_service.KnowledgeServiceTests.test_failed_import_preserves_previous_source_and_vectors`.
- `test_knowledge_service.KnowledgeServiceTests.test_failed_rebuild_does_not_publish_a_partial_profile`.

Python baseline errors, unchanged:

- `test_knowledge_answers.AnswerTests.test_compatible_chat_uses_configured_model_and_grounding_instructions`.
- `test_knowledge_providers.ProviderTests.test_cohere_uses_distinct_query_and_document_roles`.
- `test_knowledge_providers.ProviderTests.test_compatible_adapter_orders_response_vectors_and_records_usage`.
- `test_knowledge_providers.ProviderTests.test_ollama_native_adapter_and_prefixes`.

Full logs are local under `/private/tmp/saariv-ui-{node,python}-final-20261021.log`. No existing assertion was weakened to hide these failures.

## Final review

A fresh `gpt-6-astra` reviewer inspected `33c6553..1ca5eec` and independently ran the then-current 27 passing UI tests. It found no Critical or Important issues and one Minor finding: approved revisions still displayed the unconditional “Private draft” badge, with generic status text. The executor treated truthful visibility/review status as important and fixed it in the single review-fix pass. Server-rendered and live badges now distinguish private drafts, awaiting review, approved revisions, and declined review; unknown status is read-only. Two new regression tests and the live post-submit badge assertion failed before the fix and pass afterward. The updated whole Node suite is 52/52, the Python baseline is unchanged, and the actual DOM browser pass was repeated with the new badge assertion. No minor findings were deferred.

The reviewer explicitly set aside backend routing/authentication/durable resume/real authorization, money and vote ordering, vector/SQL/index behavior, draft-create retry idempotency, existing Python reliability work, and real production provider/payment acceptance. Those remain the documented integration responsibilities and release gates; the frontend review does not waive them. The review-fix pass was verified by the implementing agent; it did not trigger another full review cycle.

## Rulings and remaining gates

1. The explicit workstream assignment overrides the subplan's `app.py` edit: this branch supplies frontend files and contracts only. Route mounting and real Flask response/authorization tests remain integration work.
2. The plan omits draft JSON schemas. The adapter above uses `body` and optimistic `version`; backend code must deliberately implement or adapt it. No duplicate backend domain was added.
3. Paid unlock is visibly unavailable until the secure quote/confirmation and entitlement services exist. No simulated successful purchase or wallet mutation is exposed in the UI.
4. Guest return links use the specified `next` + opaque `query_id`; server validation/intent creation and actual provider acceptance are still required.
5. The UI preserves the narrative and treats taxonomy as metadata. No embedding/chat configuration or private owner search changed.

Remaining blockers to a live marketplace: backend route/context wiring, persisted query/draft resume, real CSRF/authentication/authorization checks, paid unlock integration, approved search/indexing, funded publication approval, and the reliability baseline repair. Existing external provider/payment/release gates in the master plan still apply. This frontend workstream does not certify those gates.
