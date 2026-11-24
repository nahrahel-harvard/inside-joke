# Inside Joke. Run `make help` for targets.
PYTHON ?= python3
VENV ?= .venv
PY := $(VENV)/bin/python
PROSPECT ?= examples/dana_brightwater.json
FORMAT ?= all
ART ?= auto
PORT ?= 8765

# Export .env (OPENROUTER_API_KEY and any IJ_* model overrides) to every recipe.
ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: help setup test lint run serve demo clean

help:
	@echo "make setup   create .venv and install pinned dependencies (pipeline + study toolkit)"
	@echo "make test    run the offline unittest suite (no API key)"
	@echo "make lint    run ruff (installs it into .venv on first use)"
	@echo "make demo    render all 5 formats offline with placeholder art into out/demo"
	@echo "make run     generate GIFs for PROSPECT=$(PROSPECT) FORMAT=$(FORMAT) ART=$(ART) (needs a key)"
	@echo "make serve   start the local web app on http://127.0.0.1:$(PORT)"

$(PY):
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-study.txt

setup: $(PY)

test: $(PY)
	$(PY) -m unittest discover -s tests -v

lint: $(PY)
	@$(PY) -m ruff --version >/dev/null 2>&1 || $(PY) -m pip install --quiet ruff
	$(PY) -m ruff check .

demo: $(PY)
	$(PY) tests/fixtures.py --out out/demo

run: $(PY)
	$(PY) forge.py $(PROSPECT) --format $(FORMAT) --art $(ART)

serve: $(PY)
	$(PY) serve.py --port $(PORT)

clean:
	rm -rf out/demo .ruff_cache
	find . -name __pycache__ -type d -not -path "./$(VENV)/*" -prune -exec rm -rf {} +
