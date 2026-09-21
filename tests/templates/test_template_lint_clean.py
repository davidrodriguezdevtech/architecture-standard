from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import copier
import pytest

from tests.templates.conftest import TEMPLATE_ROOT


@pytest.mark.parametrize(
    ("aggregate", "context"),
    [
        # Aggregate names on both sides of `ports` (domain/model import order).
        ("order", "sales"),
        ("quote", "sales"),
        ("po_line", "sales"),
        # Context names on both sides of `bootstrap` (generated-test import order):
        # `sales` sorts after it, `billing`/`accounting` sort before it.
        ("order", "billing"),
        ("po_line", "accounting"),
    ],
)
def test_given_an_aggregate_name__when_generated__then_the_project_passes_its_own_lint(
    tmp_path: Path, aggregate: str, context: str
) -> None:
    """The generated project ships ruff's isort rules; generated imports must already obey them.

    Import order depends on names (`adapters` vs `application`, the aggregate's module vs
    `ports`, the context package vs `bootstrap`), so a rename, a new aggregate name or a new
    context name can silently break it. The full E2E loop would catch that too, but it is
    excluded from the default run.
    """
    dest = tmp_path / "generated"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(dest),
        data={
            "context_name": context,
            "aggregate_name": aggregate,
            "aggregate_module": f"{aggregate}s",
        },
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )

    # An empty destination would make every lint run below pass vacuously.
    generated = sorted(p for p in dest.rglob("*.py") if p.is_file())
    assert generated, f"copier produced no Python files under {dest}"

    check = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", str(dest)],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout + check.stderr

    fmt = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "--no-cache", str(dest)],
        capture_output=True,
        text=True,
    )
    assert fmt.returncode == 0, fmt.stdout + fmt.stderr
