.PHONY: check
check:
	uv run ty check .
	uv run ruff check .
	uv run ruff format --check .
	cd web && npm run lint
	cd web && npm run format:check

.PHONY: format
format:
	uv run ruff format .
	cd web && npm run format
