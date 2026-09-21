from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import copier
import pytest

from tests.templates.conftest import TEMPLATE_ROOT


@pytest.mark.parametrize("aggregate", ["order", "quote"])
def test_given_an_aggregate_name__when_generated__then_the_project_passes_its_own_lint(
    tmp_path: Path, aggregate: str
) -> None:
    """The generated project ships ruff's isort rules; generated imports must already obey them.

    Import order depends on names (`adapters` vs `application`, the aggregate's module vs
    `ports`), so a rename or a new aggregate name can silently break it. The full E2E loop
    would catch that too, but it is excluded from the default run.
    """
    dest = tmp_path / "generated"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(dest),
        data={"aggregate_name": aggregate, "aggregate_module": f"{aggregate}s"},
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", str(dest)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
