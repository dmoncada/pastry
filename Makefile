.PHONY: check
check:
	uv run ty check .
	uv run ruff check .
	uv run ruff format --check .
	cd web && npm run lint
	cd web && npm run format:check
	tofu -chdir=infra fmt -recursive -check
	tofu -chdir=infra validate

.PHONY: format
format:
	uv run ruff format .
	cd web && npm run format
	tofu -chdir=infra fmt -recursive

.PHONY: test
test:
	uv run pytest
	cd web && npm test -- --run

.PHONY: clean
clean:
	find . -type d -name "__pycache__" -exec rm -fr {} +
	rm -fr .pytest_cache .ruff_cache .venv build
	rm -fr web/node_modules web/dist
