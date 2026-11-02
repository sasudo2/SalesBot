.PHONY: install lint type layers test check run serve ingest migrate
install:
	uv sync
lint:
	uv run ruff check .
	uv run ruff format --check .
type:
	uv run mypy app
layers:
	uv run lint-imports
test:
	uv run pytest --cov=app --cov-fail-under=85
check: lint type layers test
run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
serve:
	uv run python -m app
ingest:
	uv run python -m app.cli ingest --products data/sample/products.csv --knowledge data/sample/knowledge
migrate:
	uv run alembic upgrade head
