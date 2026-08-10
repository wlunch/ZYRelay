PYTHON ?= .venv/bin/python
PYTHON_PADDLE ?= .venv-paddleocr/bin/python

.PHONY: setup setup-paddleocr verify-models test test-model run-paddleocr samples lint format-check typecheck benchmark docker-build deploy

setup:
	$(PYTHON) -m pip install -e '.[dev]'

setup-paddleocr:
	$(PYTHON_PADDLE) -m pip install -e '.[test,paddleocr]'
	$(PYTHON_PADDLE) -m zyrelay.models install paddleocr

verify-models:
	$(PYTHON_PADDLE) -m zyrelay.models verify paddleocr

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check zyrelay tests

format-check:
	$(PYTHON) -m ruff format --check zyrelay tests

typecheck:
	$(PYTHON) -m mypy --follow-imports=skip zyrelay/app/models zyrelay/plugin/lifecycle.py zyrelay/resources/models.py zyrelay/relay/models.py

benchmark:
	$(PYTHON_PADDLE) benchmark/scripts/run_benchmark.py --suite contract --output benchmark/results/latest

test-model:
	$(PYTHON_PADDLE) -m pytest -m model_integration -q

samples:
	$(PYTHON_PADDLE) examples/create_team_code_convention_samples.py

run-paddleocr:
	$(PYTHON_PADDLE) -m uvicorn zyrelay.app.main:app --host 127.0.0.1 --port 8000

docker-build:
	docker build -t zyrelay-docintelligence:1.0.0 .

deploy:
	docker compose up --build
