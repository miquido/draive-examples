SHELL := sh
.ONESHELL:
.SHELLFLAGS := -eu -c
.DELETE_ON_ERROR:

SOURCES_PATH := src

# load environment config from .env if able
-include .env

ifndef PYTHON_ALIAS
	PYTHON_ALIAS := python
endif

ifndef UV_ALIAS
	UV_ALIAS := uv
endif

ifndef INSTALL_OPTIONS
	INSTALL_OPTIONS := .[dev]
endif

ifndef CHAINLIT_PORT
	CHAINLIT_PORT := 8888
endif

.PHONY: install venv sync lock update format lint run docker_run

# Install in system without virtual environment and extras. DO NOT USE FOR DEVELOPMENT
install:
	@echo '# Installing...'
	@echo '...preparing dependencies...'
	@pip install $(INSTALL_OPTIONS) --system --constraint constraints
	@echo '...finished!'

# Setup virtual environment for local development.
venv:
	@echo '# Preparing development environment...'
	@echo '...cloning .env...'
	@cp -n ./config/.env.example ./.env || :
	@echo '...preparing venv...'
	@$(PYTHON_ALIAS) -m venv .venv --prompt="VENV[DEV]" --clear --upgrade-deps
	@. ./.venv/bin/activate && pip install --upgrade pip && pip install --editable $(INSTALL_OPTIONS) --constraint constraints
	@echo '...development environment ready! Activate venv using `. ./.venv/bin/activate`.'

# Sync environment with uv based on constraints
sync:
	@echo '# Synchronizing dependencies...'
	@$(UV_ALIAS) pip install --editable $(INSTALL_OPTIONS) --constraint constraints
	@echo '...finished!'

# Generate a set of locked dependencies from pyproject.toml
lock:
	@echo '# Locking dependencies...'
	@$(UV_ALIAS) pip compile pyproject.toml -o constraints --all-extras
	@echo '...finished!'

# Update and lock dependencies from pyproject.toml
update:
	@echo '# Updating dependencies...'
	@$(UV_ALIAS) --no-cache pip compile pyproject.toml -o constraints --all-extras --upgrade
	@$(UV_ALIAS) pip install --editable $(INSTALL_OPTIONS) --constraint constraints
	@echo '...finished!'

# Run formatter.
format:
	@ruff --quiet --fix $(SOURCES_PATH) $(TESTS_PATH)

# Run linters and code checks.
lint:
	@bandit -r $(SOURCES_PATH)
	@ruff check $(SOURCES_PATH) $(TESTS_PATH)
	@pyright --project ./

# Run local server with hot reload.
run:
	chainlit run ./src/entrypoint/chat.py -w

# Run all services locally using docker-compose.
docker_run:
	@docker-compose up --force-recreate --build chat
