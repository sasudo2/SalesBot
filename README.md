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
# Provide NVIDIA_KEY via your Codespaces secret or environment.
# Never commit .env or tokens.
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

## Streamlit frontend

Keep the API running in one terminal:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In another terminal, launch the optional frontend:

```bash
uv sync --extra ui
uv run --extra ui streamlit run streamlit_app.py
```

Open http://localhost:8501 (forward port 8501 in Codespaces). The sidebar defaults
to `http://localhost:8000`; set the URL of the backend as reachable from the
Streamlit server, not from your browser. You can also set `SALESBOT_API_URL`.
Enter the backend's optional API key in the password field, or export `API_KEY`
before launching. The UI does not automatically load `.env`.

The UI keeps chat history and a conversation UUID in Streamlit session state,
shows the last returned cart and handoff status, and displays API errors. New
conversation resets only the UI session; it does not cancel old carts or orders.
There are no automatic retries, especially after uncertain checkout timeouts.
Use HTTPS when connecting to a remote backend with an API key. Keep this simple
development UI private; it is not a customer authentication layer.

## Backend configuration

[.env.example](.env.example) lists every settings variable and its default.
Settings are case-insensitive; arrays use JSON, e.g.
`FALLBACK_PROVIDERS=["anthropic"]`, `CORS_ORIGINS=["http://localhost:3000"]`.
Empty environment values are ignored so optional keys can remain blank.

- SQLite is the local default; production uses PostgreSQL 16 with
  `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB`.
- `DEFAULT_PROVIDER` defaults to `nvidia`. `NVIDIA_KEY` is read directly
  from the environment, including GitHub Codespaces secrets available to this
  Codespace. Actions-only secrets are not automatically available in Codespaces.
  Add/reload the Codespaces secret if necessary, then restart the backend.
- `NVIDIA_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b` selects the default NVIDIA model.
  NVIDIA uses `https://integrate.api.nvidia.com/v1` through the existing OpenAI
  SDK, including tool calls and built-in retries. Set `NVIDIA_MODEL` to another
  tool-capable model available to your key if needed. Availability, quotas, and
  billing depend on your NVIDIA account. To use NVIDIA only as a fallback, select
  another default provider and set `FALLBACK_PROVIDERS=["nvidia"]`.
- `OPENROUTER_MODEL=openrouter/free` uses OpenRouter's
  [free router](https://openrouter.ai/docs/guides/routing/routers/free-router),
  which selects a free model supporting the request's features, including tools.
  Availability, latency, quality, and rate limits vary. No paid fallback is enabled
  by default. To pin a free model, set a currently available `:free` model ID that
  supports tools; do not use `openrouter/auto` if you require free-only inference.
  Select `DEFAULT_PROVIDER=openrouter` and supply `OPENROUTER_TOKEN` to use it.
- OpenAI and Anthropic generation remain available by selecting `openai` or
  `anthropic` and supplying their respective keys. Explicitly configured paid
  fallback providers can incur charges.
- Google Gemini is available directly (not through OpenRouter) using
  `DEFAULT_PROVIDER=gemini`, `GOOGLE_TOKEN` (a Google AI Studio API key), and
  `GEMINI_MODEL=gemini-2.5-flash`. It uses Google's
  [OpenAI-compatible endpoint](https://ai.google.dev/gemini-api/docs/openai),
  so no additional SDK is required. Set `GOOGLE_TOKEN` as a Codespaces environment
  secret or in your untracked `.env`, then restart the backend. Compose passes
  these variables through as well. NVIDIA remains the default unless changed.
  To use Gemini only as fallback, set `FALLBACK_PROVIDERS=["gemini"]`.
  Google model availability, quotas, free-tier eligibility, and billing depend on
  your project; this integration does not guarantee free usage.
  Keep the 2.5 default for tool use; Gemini 3+ thought-signature round trips are
  not supported by this adapter yet. Embeddings are independent, so switching
  only the LLM provider does not require re-ingestion.
- `EMBEDDING_PROVIDER=local` runs FastEmbed on CPU using
  `LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`. Its model files download on first
  embedding use, so that first ingestion/search needs internet and can take longer.
  Later embeddings run locally with no API key or per-request API charge. The
  default model is English-oriented; Nepali retrieval quality is limited.
- To keep OpenAI embeddings, set `EMBEDDING_PROVIDER=openai`,
  `EMBEDDING_MODEL=text-embedding-3-small`, and `OPENAI_API_KEY`.
  **Re-ingest all catalogue and knowledge records after switching embedding
  providers/models.** Old vectors are not compatible; product hashes include the
  selected model. Remove obsolete records separately so old vectors are not mixed.
- `API_KEY`, when non-empty, requires `X-API-Key` on `/chat`. Set it before
  exposing the service. Put TLS, rate limits, and per-customer authorization at
  the deployment boundary; conversation UUIDs alone are not authorization.
- `EXPIRE_JOB_INTERVAL_S=0` disables the reservation-expiry background task.
  Otherwise it runs every 300 seconds; reservations expire after 60 minutes.
- Dev/test startup creates missing tables; production runs migrations explicitly.
- `ENABLE_FAKE_PROVIDER=true` registers the scripted `fake` provider. It has no
  built-in script and reports provider exhaustion until configured in code/tests.
  Offline tests override both the LLM and embedder. Local embeddings are explicitly
  configured, never used as a silent fallback after a provider failure.

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
and set `NVIDIA_KEY` in your environment or untracked `.env`. Optionally set
`NVIDIA_MODEL`, `DEFAULT_PROVIDER`, `FALLBACK_PROVIDERS`, and `API_KEY`.
Compose passes local embedding settings through too; the model cache is inside
the container unless you configure a persistent cache mount.

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