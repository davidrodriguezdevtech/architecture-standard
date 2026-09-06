.PHONY: install lint test check docs
install:
	uv sync
lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy
test:
	uv run pytest
check:
	uv run arch-standard check .
docs:
	uv run arch-standard docs
