.PHONY: install lint test check docs e2e
install:
	uv sync
lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy
test:
	uv run pytest
	uv run --package arch-commons pytest -c packages/arch-commons/pyproject.toml packages/arch-commons/tests
check:
	uv run arch-standard check .
docs:
	uv run arch-standard docs
e2e:
	uv run pytest tests/templates/test_distribution_e2e.py -m e2e -v
