# Implementation notes

## Decisions

- Shared HTTP schemas live in `app/domain/schemas.py` and are re-exported by
  `app/api/schemas.py`. The specified agent signatures need these schemas, while
  the specified import contract prohibits an agent-to-API import.
- HTTP request-ID middleware is asynchronous because it must await FastAPI's
  `call_next`; business logic, endpoints, repositories, SDKs, and tools are sync.
  Lifespan/background expiry also uses async as specified.
- The Anthropic dependency is bounded to `>=0.40,<1`: installed 1.x/2.x APIs no
  longer accept the specified `temperature` parameter.
- CLI row counts use logging, not print, following the non-negotiable logging rule.
- SQLite uses explicit BEGIN and foreign-key enforcement in production code as
  well as tests; otherwise releasing a savepoint can commit an outer request.
- Request sessions retain loaded conversation ORM roots, and saves compare domain
  versions too. SQLAlchemy's weak identity map alone cannot retain the loaded
  conversation/cart versions after conversion into detached domain models.
- Inventory updates use UPDATE RETURNING to detect zero affected rows with typed
  SQLAlchemy results. Reserve/commit operations have internal savepoints so a
  later unavailable item cannot leave earlier items partly changed.
- Cart tools reload availability after releasing their own reservation. Reading
  availability first would incorrectly count that reservation against the customer.
- Order-token replays must belong to the same conversation before returning an
  existing order. Chunking rejects invalid overlap/size, embedding adapters verify
  response counts, and whitespace-only customer names are rejected explicitly.
- Empty environment values are ignored, allowing the default example's blank
  optional credentials. Compose requires an operator-supplied URL-safe database
  password and contains no real credentials.
- `FakeProvider` remains strictly scripted and fails when exhausted; tests supply
  its responses and override embeddings.
- At the user's request, OpenRouter is now the default generation provider, reading
  `OPENROUTER_TOKEN` from the environment and using `openrouter/free`. The existing
  OpenAI wire adapter is reused with OpenRouter's base URL; paid fallbacks are opt-in.
- At the user's request, FastEmbed CPU embeddings are now the default, with a lazy,
  cached `BAAI/bge-small-en-v1.5` model download and no embedding API key required.
  `EMBEDDING_PROVIDER=openai` preserves the old option. Changing embedding models
  requires re-ingestion; the CLI hashes products with the selected model ID.
- Mypy skips FastEmbed internals and unrelated OpenAI SDK API families to keep
  memory use bounded; the application's strict checking and Chat Completions
  request types remain enabled.
- Existing unrelated data, editor/devcontainer configuration, docs, and `hello.py`
  are preserved. Ruff excludes the unrelated legacy `hello.py`; the old prototype
  modules were replaced by the specified package layout. The implementation and
  `uv.lock` are committed together with user approval.

## Validation and limitations

- Each build phase runs `make check`, fixing failures before advancing.
- Initial backend build `make check`: Ruff checks pass (105 files formatted), strict mypy passes
  (80 source files), one import-layer contract kept, 67 tests pass, coverage 99.76%.
- Both `uvicorn app.main:app` and `python -m app` pass live subprocess health checks;
  the wheel/source distribution build succeeds.
- Offline tests cover SQLite migrations, provider SDK mapping/fallback, retrieval,
  cart/order invariants, savepoint restoration, request rollback, HTTP errors,
  three-turn checkout, same-turn rejection, and real uvicorn startup.
- The OpenRouter update was verified with an authenticated `openrouter/free`
  tool call using synthetic text only. Local CPU embeddings were verified with
  three synthetic inputs producing 384-dimensional vectors. No catalogue or
  customer data was sent during these checks.
- OpenRouter/local embedding regression validation: 85 tests passed, coverage
  99.59%, strict mypy passed on 82 application files, import-layer contract kept.
  The legacy sample CLI test was deselected because the user removed its
  `data/sample/products.csv` input; new self-contained CLI tests verify selection
  of both local and OpenAI embedding model IDs.
- Explicit affirmative
  customer intent is interpreted by the LLM under the system prompt; deterministic
  server checks enforce token, unchanged-cart, and later-turn requirements.
- Docker is not installed in the build environment. Compose runtime, image startup,
  and PostgreSQL integration cannot be certified here. Compose YAML, PostgreSQL ORM
  DDL compilation, and offline PostgreSQL migration SQL generation pass, but are
  not substitutes for `docker compose up` on a Docker host.
- This is not a payment processor or channel webhook gateway. Authentication is a
  shared API key, not per-customer conversation authorization. Add deployment-level
  TLS, rate limits, and customer access control before public exposure.
