.PHONY: check
check:
	uv run ruff check .
	uv run ruff format --check .
	cd web && npm run lint
	cd web && npm run format:check
