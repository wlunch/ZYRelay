PYTHON ?= .venv/bin/python
PYTHON_PADDLE ?= .venv-paddleocr/bin/python

.PHONY: setup setup-paddleocr verify-models test test-model run-paddleocr samples

setup:
	$(PYTHON) -m pip install -e '.[dev]'

setup-paddleocr:
	$(PYTHON_PADDLE) -m pip install -e '.[test,paddleocr]'
	$(PYTHON_PADDLE) -m zyrelay.models install paddleocr

verify-models:
	$(PYTHON_PADDLE) -m zyrelay.models verify paddleocr

test:
	$(PYTHON) -m pytest -q

test-model:
	$(PYTHON_PADDLE) -m pytest -m model_integration -q

samples:
	$(PYTHON_PADDLE) examples/create_team_code_convention_samples.py

run-paddleocr:
	$(PYTHON_PADDLE) -m uvicorn zyrelay.app.main:app --host 127.0.0.1 --port 8000
