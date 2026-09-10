# tests/templates/test_generated_project_end_to_end.py
from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import copier
import pytest

from arch_standard.cli import main
from tests.templates.conftest import TEMPLATE_ROOT

_COMMONS_SRC = Path(__file__).resolve().parents[2] / "packages" / "arch-commons" / "src"

_GENERATED_MODULE_PREFIXES = ("bootstrap", "sales", "commons")


def _reset_generated_modules() -> None:
    for name in list(sys.modules):
        if name.startswith(_GENERATED_MODULE_PREFIXES):
            del sys.modules[name]


@pytest.fixture(autouse=True)
def _clean_module_cache() -> Generator[None, None, None]:
    _reset_generated_modules()
    yield
    _reset_generated_modules()


def test_given_a_freshly_generated_project__when_service_runs__then_order_is_created_and_event_published(  # noqa: E501
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(str(TEMPLATE_ROOT), str(dest), defaults=True, overwrite=True, unsafe=True)

    monkeypatch.syspath_prepend(str(dest / "src"))
    monkeypatch.syspath_prepend(str(_COMMONS_SRC))

    import importlib

    bootstrap = importlib.import_module("bootstrap")
    container = bootstrap.build_container()

    order_service_module = importlib.import_module("sales.orders.application.order_service")
    order_id = container.order_service.create_order(order_service_module.CreateOrder(name="widget"))

    assert order_id.value

    bus = container.order_service._bus
    assert len(bus.published) == 1


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
