from __future__ import annotations

from pathlib import Path

import copier

from tests.templates.conftest import TEMPLATE_ROOT


def test_given_defaults__when_copied__then_root_files_render_with_no_leftover_jinja(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "generated"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(dest),
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )

    for relative in ("main.py", "pyproject.toml", "contexts.toml", ".arch-standard", "Makefile"):
        content = (dest / relative).read_text(encoding="utf-8")
        assert "{{" not in content, f"{relative} has unrendered Jinja: {content!r}"

    assert (dest / ".github" / "workflows" / "ci.yml").is_file()
    assert 'name = "sales"' not in (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert "[contexts.sales]" in (dest / "contexts.toml").read_text(encoding="utf-8")
    assert 'standard-version = "0.1.0"' in (dest / ".arch-standard").read_text(encoding="utf-8")


def test_given_index_source__when_rendered__then_deps_have_no_git_url(tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(dest),
        data={"dependency_source": "index"},
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )
    text = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert "arch-standard==" in text
    assert "git+" not in text


def test_given_git_source__when_rendered__then_deps_use_the_supplied_url(tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(dest),
        data={
            "dependency_source": "git",
            "standard_git_url": "https://example.invalid/standard.git",
        },
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )
    text = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert "git+https://example.invalid/standard.git" in text


def test_given_the_template__when_reading_config__then_no_change_me_placeholder() -> None:
    text = (TEMPLATE_ROOT / "copier.yml").read_text(encoding="utf-8")
    assert "CHANGE_ME" not in text
