# One venv per clone (.venv), one pyproject per package. Works in Git Bash on Windows and on macOS/Linux.
SHELL := bash
ifneq ($(wildcard .venv/Scripts/python.exe),)
  VENV_BIN := .venv/Scripts
else
  VENV_BIN := .venv/bin
endif
PY := $(VENV_BIN)/python
PORT ?= 8000
# DATA_DIR defaults to ~/junction-data (server/src/server/config.py); export DATA_DIR=... to override

.PHONY: help setup dev server web web-build test smoke fixtures mcp share

help:
	@echo "make setup      venv + all python packages (editable) + web deps"
	@echo "make dev        server on :$(PORT) (reload) + web dev server"
	@echo "make server     server only on :$(PORT)"
	@echo "make test       all python tests"
	@echo "make smoke      end-to-end smoke (throwaway local server; API_URL=... to target another)"
	@echo "make fixtures   regenerate data/fixtures/ from the fake engine"
	@echo "make mcp        MCP server over stdio (API_URL=... to proxy to a running server)"
	@echo "make web-build  build web/dist (served by the server at /)"
	@echo "make share      expose :$(PORT) via cloudflared quick tunnel"

$(PY):
	python -m venv .venv
	$(PY) -m pip install -q --upgrade pip

setup: $(PY)
	$(PY) -m pip install -q -e ./engine -e ./server[test] -e ./arena -e ./analysis pytest
	@if [ -f web/package.json ]; then (cd web && npm install); fi

server:
	$(PY) -m server serve --port $(PORT)

dev:
	@trap 'kill 0' EXIT; \
	$(PY) -m server serve --port $(PORT) --reload & \
	if [ -f web/package.json ]; then (cd web && npm run dev); else wait; fi

web:
	cd web && npm run dev

web-build:
	cd web && npm run build

test:
	$(PY) -m pytest -q server/tests $(wildcard engine/tests) $(wildcard arena/tests) $(wildcard analysis/tests)

smoke:
	bash scripts/smoke.sh

fixtures:
	$(PY) scripts/make_fixtures.py

mcp:
	$(PY) -m server mcp $(if $(API_URL),--api $(API_URL),)

share:
	cloudflared tunnel --url http://localhost:$(PORT)
