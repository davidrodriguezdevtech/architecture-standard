# tests/templates/test_generated_project_end_to_end.py
from __future__ import annotations

from pathlib import Path

import copier
import pytest

from arch_standard.cli import main
from tests.templates.conftest import TEMPLATE_ROOT


def test_given_a_freshly_generated_project__when_render_importlinter_and_check__then_core_rules_pass(  # noqa: E501
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(
        str(TEMPLATE_ROOT), str(dest), defaults=True, overwrite=True, unsafe=True, skip_tasks=True
    )

    # Simulates copier.yml's `_tasks` entry (a real `arch-standard render-importlinter .`
    # subprocess at generation time) in-process, so this test does not depend on PATH
    # resolution inside the test's own subprocess environment.
    render_exit_code = main(["render-importlinter", str(dest)])
    assert render_exit_code == 0

    check_exit_code = main(["check", str(dest), "--core"])
    output = capsys.readouterr().out

    # ARCH-033 (Task 9) now has a real AST check; the generated service commits
    # through `with self._uow: ... self._uow.commit()`, which the check
    # recognizes as committing through the entered Unit of Work. ARCH-008 is
    # attributed to the per-module layers contract (Task 6). Both genuinely
    # pass, so the generated project violates nothing: no FAIL rows, exit 0.
    assert check_exit_code == 0, output
    assert "FAIL" not in output
