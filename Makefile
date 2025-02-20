.PHONY: lint
lint:
	uvx ruff check --fix
	uvx ruff format
	uv run mypy

.PHONY: test
test:
	uv run pytest
