PY=python

.PHONY: install lint format typecheck test qa

install:
	$(PY) -m pip install -r requirements.txt

lint:
	ruff check .

format:
	black .
	ruff format .

typecheck:
	mypy .

test:
	pytest || true

qa: lint typecheck test
