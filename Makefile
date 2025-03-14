# ================ COLORS ================

RED     := $(shell tput -Txterm setaf 1)
GREEN   := $(shell tput -Txterm setaf 2)
YELLOW  := $(shell tput -Txterm setaf 3)
BLUE    := $(shell tput -Txterm setaf 4)
PURPLE  := $(shell tput -Txterm setaf 5)
CYAN    := $(shell tput -Txterm setaf 6)
WHITE   := $(shell tput -Txterm setaf 7)
BOLD   := $(shell tput -Txterm bold)
RESET   := $(shell tput -Txterm sgr0)

# ================ COMMANDS ================
.PHONY: start-redis stop-redis
## Start Redis in a Docker container
start-redis:
	-docker rm --force redis || true
	docker run --name redis --detach --publish 6379:6379 redis

## Stop the Redis Docker container
stop-redis:
	docker stop redis

.PHONY: start-valkey stop-valkey
## Start Valkey in a Docker container
start-valkey:
	-docker rm --force valkey || true
	docker run --name valkey --detach --publish 6379:6379 valkey/valkey

## Stop the Valkey Docker container
stop-valkey:
	docker stop valkey

.PHONY: start-memcached stop-memcached
## Start Memcached in a Docker container
start-memcached:
	-docker rm --force memcached || true
	docker run --name memcached --detach --publish 11211:11211 memcached

## Stop the Memcached Docker container
stop-memcached:
	docker stop memcached

.PHONY: venv
## Create a virtual environment
venv:
	uv venv --allow-existing

.PHONY: install
## Install the project in development mode
install: venv
	uv sync --all-extras --dev
	uv pip install --no-deps --upgrade --editable .

.PHONY: lint
## Run linters
lint: install
	uvx ruff check --fix
	uvx ruff format
	uv run mypy

.PHONY: test unit-test integration-test
## Run all tests
test: unit-test integration-test

## Run unit tests
unit-test: install
	uv run pytest -vv --cov --cov-report html \
		--cov-report term-missing --cov-report xml \
		--no-cov-on-fail --cov-fail-under 100 \
		tests/unit

## Run integration tests
integration-test: install start-redis start-memcached
	uv run pytest -vv tests/integration

# ================ HELP ================
# In order to add a help text to your command, add the following '## YOUR HELP MESSAGE' above it
# Adapted from https://gist.github.com/prwhite/8168133

TARGET_MAX_CHAR_NUM=15

.PHONY: help
help:
	@echo ''
	@echo '${CYAN}${BOLD}Usage:${RESET}'
	@echo '  ${YELLOW}${BOLD}make${RESET} ${WHITE}[target]${RESET}'
	@echo ''
	@echo '${CYAN}${BOLD}Targets:${RESET}'
	@awk '/^[[:alnum:]_\-]+:/ { \
	    helpCommand = substr($$1, 0, index($$1, ":")-1); \
	    if (helpCommand != "help") { \
	        msgMatch = match(lastLine, /^## (.*)/); \
	        helpMessage = substr(lastLine, RSTART + 3, RLENGTH); \
	        printf "  ${YELLOW}${BOLD}%-$(TARGET_MAX_CHAR_NUM)s${RESET} ${WHITE}%s${RESET}\n", helpCommand, helpMessage; \
	    } \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)
	@echo ''
