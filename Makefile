.PHONY: install
install:
	uv sync --all-extras --dev
	uv pip install --upgrade --editable .

.PHONY: lint
lint: install
	uvx ruff check --fix
	uvx ruff format
	uv run mypy

.PHONY: test
test: install
	uv run pytest
