from __future__ import annotations

from pathlib import Path

from arch_standard.checks.base import (
    CheckReport,
    Finding,
    Outcome,
    ProjectLayout,
    iter_python_files,
)

GOOD = Path(__file__).parent.parent / "fixtures" / "good_project"


def test_detect_finds_contexts_excluding_infra_dirs() -> None:
    layout = ProjectLayout.detect(GOOD)
    assert layout.contexts == ("sales",)
    assert layout.src == GOOD / "src"


def test_detect_finds_no_contexts_on_a_non_ddd_tree(tmp_path: Path) -> None:
    # I5: a directory under src/ is only a context if it actually contains one
    # of the DDD layer dirs — otherwise any src/ subpackage (e.g. this very
    # package, `src/arch_standard/`) is wrongly treated as a bounded context.
    (tmp_path / "src" / "somepkg").mkdir(parents=True)
    (tmp_path / "src" / "somepkg" / "foo.py").write_text("x = 1\n")
    layout = ProjectLayout.detect(tmp_path)
    assert layout.contexts == ()


def test_module_dirs_resolve_under_good_project() -> None:
    # domain_dir/application_dir/infrastructure_dir were removed in Task 10: every
    # fixture now has aggregate modules, so only the module-scoped accessors resolve
    # real paths.
    layout = ProjectLayout.detect(GOOD)
    assert layout.module_domain_dir("sales", "orders") == GOOD / "src/sales/orders/domain"
    assert layout.module_application_dir("sales", "orders") == GOOD / "src/sales/orders/application"
    assert layout.entrypoints_dir("sales") == GOOD / "src/sales/entrypoints"


def test_iter_python_files_skips_pycache(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "b.py").write_text("y = 2\n")
    found = {p.name for p in iter_python_files(tmp_path)}
    assert found == {"a.py"}


def test_check_report_is_frozen_dataclass() -> None:
    r = CheckReport(rule_id="ARCH-001", outcome=Outcome.PASS)
    assert r.findings == ()
    f = Finding(rule_id="ARCH-001", path="x.py", line=3, message="boom")
    assert f.line == 3


def _make_modular(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for rel in [
        "src/sales/entrypoints/http.py",
        "src/sales/shared/ids.py",
        "src/sales/read/customer_overview.py",
        "src/sales/users/domain/model/user.py",
        "src/sales/users/application/user_service.py",
        "src/sales/users/adapters/user_repository.py",
        "src/sales/orders/domain/model/order.py",
        "src/sales/orders/application/order_service.py",
    ]:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("", encoding="utf-8")
    return root


def test_given_modular_tree__when_detect__then_context_found(tmp_path: Path) -> None:
    layout = ProjectLayout.detect(_make_modular(tmp_path))
    assert layout.contexts == ("sales",)


def test_given_modular_tree__when_modules__then_reserved_dirs_excluded(tmp_path: Path) -> None:
    layout = ProjectLayout.detect(_make_modular(tmp_path))
    assert layout.modules("sales") == ("orders", "users")


def test_given_modular_tree__when_module_dirs__then_paths_are_nested(tmp_path: Path) -> None:
    root = _make_modular(tmp_path)
    layout = ProjectLayout.detect(root)
    assert layout.module_domain_dir("sales", "users") == root / "src/sales/users/domain"
    assert layout.module_application_dir("sales", "users") == root / "src/sales/users/application"
    assert layout.module_adapters_dir("sales", "users") == root / "src/sales/users/adapters"
    assert layout.shared_dir("sales") == root / "src/sales/shared"
    assert layout.read_dir("sales") == root / "src/sales/read"


def test_given_modular_tree__when_iter_modules__then_sorted_pairs(tmp_path: Path) -> None:
    layout = ProjectLayout.detect(_make_modular(tmp_path))
    assert list(layout.iter_modules()) == [("sales", "orders"), ("sales", "users")]


def test_given_dir_without_layers__when_modules__then_not_a_module(tmp_path: Path) -> None:
    root = _make_modular(tmp_path)
    (root / "src/sales/notes").mkdir()
    (root / "src/sales/notes/readme.py").write_text("", encoding="utf-8")
    layout = ProjectLayout.detect(root)
    assert "notes" not in layout.modules("sales")


MODULAR = Path(__file__).parent.parent / "fixtures" / "modular_project"


def test_given_modular_fixture__when_detect__then_two_contexts() -> None:
    layout = ProjectLayout.detect(MODULAR)
    assert layout.contexts == ("billing", "sales")


def test_given_modular_fixture__when_iter_modules__then_all_aggregate_modules() -> None:
    layout = ProjectLayout.detect(MODULAR)
    assert list(layout.iter_modules()) == [
        ("billing", "invoices"),
        ("sales", "orders"),
        ("sales", "users"),
    ]
