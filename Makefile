.PHONY: install lint test check selfcheck docs e2e
install:
	uv sync
lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy
test:
	uv run pytest
	uv run --package arch-commons pytest -c packages/arch-commons/pyproject.toml packages/arch-commons/tests
check:
	uv run arch-standard check .
selfcheck:
	uv run arch-standard check tests/fixtures/good_project
	uv run arch-standard check tests/fixtures/modular_project
	if uv run arch-standard check tests/fixtures/bad_project; then echo "bad_project passed -- the validator is not detecting violations"; exit 1; fi
	uv run arch-standard release-check --version 0.1.0
docs:
	uv run arch-standard docs
e2e:
	uv run pytest tests/templates/test_distribution_e2e.py -m e2e -v
