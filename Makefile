.PHONY: lint
lint:
	uvx ruff check --fix
	uvx ruff format

.PHONY: test
test:
	uv run pytest
