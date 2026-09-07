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
