# Marketplace RAG baseline results — Task 0.1

Date: 2026-10-21 (Asia/Singapore).
Worktree: `/Users/asali/Documents/New project 3/saariv/.worktrees/marketplace-rag`.
Branch: `codex/marketplace-rag-baseline`.
Starting commit: `33c65533d3d80067d09d104fd3649584f2d8bba3`.
Implementation commit: `acf22b4` (`fix: preserve RAG sources and exact evidence on indexing failures`).

Only Task 0.1 from [the foundation plan](2026-10-21-marketplace-foundation-auth.md) was implemented. Changes are confined to existing RAG code, its Python tests, and the import/evidence paths in `app.py`. The existing SQLite source-publication transaction was retained; no marketplace schema, route registration, dependency, environment, migration, template, or JavaScript file was changed.

## Reproduced baseline and root causes

The supplied baseline was reproduced separately for all five affected modules before implementation: 47 tests across those modules, eight failures and four errors. The other eight existing Python tests bring the original suite to 55. No failure was attributed to another workstream or suppressed.

| Original case | Classification and cause | Repair |
| --- | --- | --- |
| `test_empty_story_or_headings_without_narrative_are_rejected`, three failing subcases | Behavior defect. Empty, whitespace-only, and headings-only stories raised validation errors, but the broad step 4 exception handler converted them to HTTP 500. | Validate narrative before ingest and let the existing typed handler return HTTP 400. Added non-string and invalid-replacement coverage. |
| `test_failed_first_import_retries_using_the_signed_browser_cookie` | Behavior defect. The same blanket HTTP 500 prevented the expected failed-validation flow. | HTTP 400 leaves the signed browser owner intact; retry saves under the same owner. Added a provider-outage first-import HTTP 503/retry case. |
| `test_extract_mode_preserves_asked_wording_and_returns_citations` | Stale assertion: the confirmed presentation voice is first person, so the reply should say “I asked.” A separate real defect rewrote source text while retaining the original offsets. | Keep the first-person reply; return raw `sources[].text` with unchanged offsets and a separate `display_text`. Unicode and asked/planned/completed claims are covered. |
| `test_equal_dimensions_do_not_allow_mixing_model_profiles` | Behavior defect. `_check_profile` was disabled, and ingest deleted the owner's documents when profiles differed. | Enforce profile identity, including equal-dimensional models, before publication. Preserve all sources and vectors until an explicit successful rebuild. |
| `test_failed_import_preserves_previous_source_and_vectors` | Behavior defect. `_publish` swallowed provider failures, published replacement text as lexical, and pruned the previous vectors. | Propagate failure, retain the old SQL generation/profile/vectors, and clean only inactive staged data. Added multi-document/later-batch failure coverage. |
| `test_failed_rebuild_does_not_publish_a_partial_profile` | Behavior defect. The same lexical fallback replaced the active profile on a failed rebuild. | Failed rebuild retains the previous profile and vectors; lexical reads and the previous compatible provider remain usable. |
| Three provider adapter errors: compatible ordering/usage, Cohere roles, Ollama prefixes | Stale HTTP mocks. Their `urlopen` side effects did not accept the actual `context` keyword; the resulting `TypeError` was translated to invalid JSON. | Accept the actual signature and assert timeout, HTTPS certificate/hostname verification, and HTTP's absent context. Retain ordering, usage, role and prefix assertions. |
| Compatible chat model/grounding error | Same stale HTTP mock signature. The request never reached its capture list. | Accept and verify the TLS context and 45-second timeout; retain independent chat-model and grounding assertions. |

## Behavior and interfaces

- Source text, chunks, and vector points are prepared before the active source transaction is published. Failed embedding batches do not replace documents, remove the working vectors, or downgrade the owner's profile.
- An embedding profile change returns `ReindexRequired` (HTTP 409 with `needs_reindex: true`) for imports and semantic search. `POST /api/knowledge/reindex` is the explicit switch. Lexical reads remain available while a rebuild is required.
- Switching configured embeddings off also requires explicit reindex before imports can remove an existing semantic index. A successful explicit lexical rebuild keeps the source documents and removes the old vectors. Enabling embeddings for a lexical corpus requires rebuild before dense search.
- Embedding outages return `ProviderError`/HTTP 503. There is no success response claiming hybrid retrieval after silently saving a lexical replacement. Unconfigured embeddings continue to report lexical mode, and explicit dense retrieval is unavailable.
- Onboarding no longer deletes sources, string-matches exceptions to retry, automatically rebuilds, or temporarily mutates the shared provider. One owner's failed save does not change another owner's search configuration.
- `/api/playground/rag-query` returns exact raw `sources[].text`; `sources[].source.start/end` refer to that raw source. `sources[].display_text` is the first-person presentation. Extractive replies retain first-person wording and asked/planned/completed distinctions. Generated answers still consume raw evidence independently of the embedding model. `/api/knowledge/search` remains raw.
- Browser ownership, read-only agent token scope, owner filters, taxonomy-only Prompt 1, narrative Prompt 2, and the no-fabricated-biography behavior remain intact.

## Verification

All provider inputs and profiles were synthetic. No real `.env`, private profiles, or API credentials were read or copied. The installed python-dotenv lacks the `PYTHON_DOTENV_DISABLED` switch, so a scratch test runner patched `dotenv.load_dotenv` **before importing the application**. Its contents were:

```python
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd()))
with patch("dotenv.load_dotenv", return_value=False):
    unittest.main(module=None, argv=[sys.argv[0], "discover", "-s", "tests", *sys.argv[1:]])
```

Exact Python command executed from the worktree (the runner was ignored scratch, removed after review; recreate it with the contents above to repeat):

```sh
env CHAT_PROVIDER=extractive EMBEDDING_PROVIDER=none OPENAI_API_KEY= CHAT_API_KEY= EMBEDDING_API_KEY= FLASK_SECRET_KEY=synthetic-rag-regression-signing-secret \
  '/Users/asali/Documents/New project 3/saariv/.venv-rag/bin/python' \
  .superpowers/sdd/2026-10-21-marketplace-foundation-auth/run_tests.py -v
```

For the required module-level reproductions, the same command used `-p test_knowledge_service.py -v` and the corresponding four other filenames. Before implementation, the focused regression runs failed for the intended preservation, profile, HTTP status, and raw-citation defects.

| Verification | Result |
| --- | --- |
| `test_knowledge_service.py` | 19 passed (original 15) |
| `test_experience_story.py` | 6 passed (original 5) |
| `test_knowledge_api.py` | 20 passed (original 16) |
| `test_knowledge_providers.py` | 7 passed |
| `test_knowledge_answers.py` | 4 passed |
| Full Python discovery, including chunking/evaluation | **64 passed, zero failures/errors** (original 55) |
| `/opt/homebrew/bin/node --test tests/*.mjs` | **23 passed, zero failures/skips** |
| `git -c core.fsmonitor=false diff --check` | Passed |

The execution skill's task completion gate reran full Python discovery after the implementation commit: 64 passed. Expected fault-injection warnings were logged. The existing PyPDF2 deprecation and SQLite connection ResourceWarning also remain; neither produced a failed test and neither was hidden.

Native PostgreSQL availability was verified with this read-only command after the ordinary sandbox denied local TCP access:

```sh
/opt/homebrew/opt/postgresql@16/bin/psql \
  'postgresql://saariv_dev@127.0.0.1:55432/saariv_marketplace_test' \
  -X -Atc 'SELECT current_database()'
```

It returned `saariv_marketplace_test`. RAG tests use disposable source/vector directories and did not mutate PostgreSQL. No non-test database was used.

## Review and coordinator handoff

A single fresh-context read-only review of `33c6553..acf22b4` completed using the execution skill. Verdict: ready for Task 0.1 integration, with **no Critical or Important findings**. The reviewer inspected the complete diff and relevant service/store/onboarding/web/provider code; it did not rerun tests or modify files.

Deferred minor: `tests/test_knowledge_service.py:129` covers failure in a later embedding batch before vector staging. Additional injected partial-vector-write and post-staging SQLite publication failures would strengthen coverage of cleanup/restart behavior. Inspection found the implementation sound; no observed data-loss defect remains. This extra coverage was deferred under the execution skill's minor-findings rule.

Required frontend integration: `static/js/main.js:1080` currently sets the excerpt from `source.text`. The coordinator/frontend workstream must prefer `source.display_text ?? source.text` to keep first-person excerpt presentation while preserving raw citation evidence. JavaScript was explicitly outside this workstream. First-person answer replies are already preserved; full UI presentation depends on that consumer update.

Profile conflicts now require the existing explicit rebuild action; a save no longer implicitly discards or rebuilds sources. Live provider acceptance remains an integration/release gate, since this work deliberately used deterministic fixtures only.

The branch/worktree are kept for the coordinator. There was no push, PR, merge, deployment, or real financial action.

## Decisions made within the scoped authorization

- Reused the coordinator's existing linked worktree and installed runtime. No dependency installation or new worktree was needed; the verified suite checks the supplied runtime, not a fresh installation.
- Patched dotenv loading only in the test runner because the installed version does not honor the disable environment variable. This avoids real configuration and secrets; live environment acceptance is consequently outside the deterministic test evidence.
- Required explicit rebuild when embeddings are disabled as well as when their profile changes. This protects working vectors; the tradeoff is one explicit rebuild action before importing under the changed configuration.
- Preserved the local branch/worktree for the coordinator, following the explicit no-push/no-PR/no-merge instructions. Integration remains the coordinator's action.
- Treated the frontend `display_text` consumer as a required coordinator handoff, since JavaScript edits were prohibited. Until that update, the excerpt UI can show the original second-person text even though answer replies and the separate display field are first person.
- Set aside OAuth state/nonce/session, return navigation, provider email, and account ownership-claim work because those belong to the other foundation tasks. These changes do not establish OAuth readiness.
- Set aside marketplace publication, entitlements, PostgreSQL search, outbox jobs, and financial behavior because Task 0.1 owns the private RAG baseline. Passing these tests does not establish marketplace or payment readiness.
- Set aside live-provider availability/model relevance because no real provider requests were authorized for these tests. Request contracts are verified; live model behavior remains unverified.
- Set aside multi-process Qdrant operation and abrupt-process/power-loss recovery because this baseline uses serialized single-process storage and exception paths. These results do not establish shared-process or crash-durability guarantees.
