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


def test_layer_dirs() -> None:
    layout = ProjectLayout.detect(GOOD)
    assert layout.domain_dir("sales") == GOOD / "src" / "sales" / "domain"
    assert layout.application_dir("sales") == GOOD / "src" / "sales" / "application"


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
