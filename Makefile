.PHONY: start-redis stop-redis
start-redis:
	docker run --name redis-it --detach --publish 6379:6379 redis
stop-redis:
	docker stop redis-it

.PHONY: start-valkey stop-valkey
start-valkey:
	docker run --name valkey-it --detach --publish 6379:6379 valkey

stop-valkey:
	docker stop valkey-it

.PHONY: start-memcached stop-memcached
start-memcached:
	docker run --name memcached-it --detach --publish 11211:11211 memcached

stop-memcached:
	docker stop memcached-it

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
