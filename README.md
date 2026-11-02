# SalesBot / Himal Mart sales agent

A synchronous FastAPI backend for catalogue search, policy retrieval, carts, and
confirmed orders in NPR. LLM tools run sequentially in a bounded loop. A failed
tool rolls back its savepoint and restores in-memory state; a failed request rolls
back the whole transaction. Stock reservations and single-use checkout tokens
protect checkout, and optimistic versions detect conflicting conversation saves.

## Local setup (Python 3.12+ and uv)

```bash
uv sync --frozen
cp .env.example .env
# Set OPENAI_API_KEY in .env. Never commit .env.
uv run alembic upgrade head
uv run python -m app.cli ingest \
  --products data/sample/products.csv --knowledge data/sample/knowledge
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Equivalent configurable entry point:

```bash
uv run python -m app
```

Both use uvicorn with the import string `app.main:app`. Module startup reads
`SERVER_HOST`, `SERVER_PORT`, `SERVER_RELOAD`, and `LOG_LEVEL`. Production must not
enable reload; multiple processes can use uvicorn's `--workers N`.

The only application endpoints are `POST /chat` and `GET /health`; FastAPI also
provides its standard schema/docs routes. `/health` is public and reports database
availability. `/chat` creates an unknown client-supplied UUID on first use.
Request IDs are echoed/generated in `X-Request-ID` and included in errors.

## Configuration

[.env.example](.env.example) lists every settings variable and its default.
Settings are case-insensitive; arrays use JSON, e.g.
`FALLBACK_PROVIDERS=["anthropic"]`, `CORS_ORIGINS=["http://localhost:3000"]`.
Empty environment values are ignored so optional keys can remain blank.

- SQLite is the local default; production uses PostgreSQL 16 with
  `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB`.
- `DEFAULT_PROVIDER` defaults to `openai`. Configure `OPENAI_API_KEY` and/or
  `ANTHROPIC_API_KEY`, then select a default and optional fallbacks.
- Embeddings use OpenAI, including when Anthropic generates replies:
  `OPENAI_API_KEY` is required for catalogue/policy retrieval and ingestion.
- `API_KEY`, when non-empty, requires `X-API-Key` on `/chat`. Set it before
  exposing the service. Put TLS, rate limits, and per-customer authorization at
  the deployment boundary; conversation UUIDs alone are not authorization.
- `EXPIRE_JOB_INTERVAL_S=0` disables the reservation-expiry background task.
  Otherwise it runs every 300 seconds; reservations expire after 60 minutes.
- Dev/test startup creates missing tables; production runs migrations explicitly.
- `ENABLE_FAKE_PROVIDER=true` registers the scripted `fake` provider. It has no
  built-in script and reports provider exhaustion until configured in code/tests.
  Offline tests override both the LLM and embedder; there is deliberately no local
  embedding fallback.

The sample data is illustrative shop policy and pricing, not a live business feed.
Ingestion overwrites stock fields from the CSV: do not re-ingest stale stock while
orders/reservations are active.

## Three-turn curl conversation

With the sample catalogue ingested and the server running, reuse the same UUID:

```bash
CONVERSATION_ID=9ed87610-c73d-4ed1-bffd-eef35cf30264
# If API_KEY is configured, add -H "X-API-Key: $API_KEY" to each request.
curl -sS http://localhost:8000/chat -H 'Content-Type: application/json' \
  -d "{\"conversation_id\":\"$CONVERSATION_ID\",\"query\":\"I want 2 chiura\",\"channel\":\"web\"}"

curl -sS http://localhost:8000/chat -H 'Content-Type: application/json' \
  -d "{\"conversation_id\":\"$CONVERSATION_ID\",\"query\":\"my name is Sita, 9841234567\"}"

# Send only after the assistant shows the total and asks for confirmation.
curl -sS http://localhost:8000/chat -H 'Content-Type: application/json' \
  -d "{\"conversation_id\":\"$CONVERSATION_ID\",\"query\":\"yes\"}"
```

Replies contain `{conversation_id, reply, handoff, cart}`. Prices serialize as
decimal strings. Clients never supply checkout tokens: those remain in the tool
conversation. Provider wording may vary; deterministic offline acceptance tests
verify the same flow, inventory arithmetic, logs, and same-turn rejection.

Errors contain `{code, message, request_id}`. Validation errors return 422,
domain conflicts 409, provider failures 502/503, and unexpected failures a generic
500 without internal details. Handoff conversations bypass the LLM on later turns.

## Docker / PostgreSQL

Set `POSTGRES_PASSWORD` to a strong alphanumeric password (to remain URL-safe),
and set `OPENAI_API_KEY` in your environment or untracked `.env`. Optionally set
`ANTHROPIC_API_KEY`, `DEFAULT_PROVIDER`, `FALLBACK_PROVIDERS`, and `API_KEY`.

```bash
docker compose up --build -d
curl -f http://localhost:8000/health
docker compose exec api python -m app.cli ingest \
  --products data/sample/products.csv --knowledge data/sample/knowledge
```

The image runs as a non-root user. Compose waits for PostgreSQL, runs
`alembic upgrade head`, then starts:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

PostgreSQL data persists in the `postgres_data` named volume. Do not remove the
volume unless intentionally discarding your database.

## Tests and quality gate

```bash
make check
# Focused deterministic checkout + real uvicorn smoke test:
uv run pytest tests/test_e2e_order_flow.py tests/test_uvicorn_smoke.py -v
```

`make check` runs Ruff lint/format checks, strict mypy on `app/`, import-layer
contracts, and offline pytest with at least 85% coverage. Tests use transactional
SQLite, mocked SDK clients, a scripted LLM, and a deterministic test-only embedder.
The smoke test starts a real uvicorn subprocess, checks `/health`, and terminates it.

Other targets: `install`, `lint`, `type`, `layers`, `test`, `run`, `serve`, `ingest`,
and `migrate`. The legacy `requirements.txt` now points at this same project rather
than maintaining a second dependency set.

See [NOTES.md](NOTES.md) for specification decisions and validation limitations.