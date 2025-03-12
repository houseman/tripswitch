.PHONY: start-redis stop-redis
start-redis:
	-docker rm --force redis || true
	docker run --name redis --detach --publish 6379:6379 redis
stop-redis:
	docker stop redis

.PHONY: start-valkey stop-valkey
start-valkey:
	-docker rm --force valkey || true
	docker run --name valkey --detach --publish 6379:6379 valkey/valkey

stop-valkey:
	docker stop valkey

.PHONY: start-memcached stop-memcached
start-memcached:
	-docker rm --force memcached || true
	docker run --name memcached --detach --publish 11211:11211 memcached

stop-memcached:
	docker stop memcached

.PHONY: venv
venv:
	uv venv --allow-existing --python=python3.9

.PHONY: install
install: venv
	uv sync --all-extras --dev
	uv pip install --upgrade --editable .

.PHONY: lint
lint: install
	uvx ruff check --fix
	uvx ruff format
	uv run mypy

.PHONY: test
test: install
	uv run pytest -vv
