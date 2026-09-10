from __future__ import annotations

import os
import subprocess
from pathlib import Path

import copier
import pytest

REPO = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = REPO / "templates"


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise AssertionError(
            f"command failed ({done.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{done.stdout}\n--- stderr ---\n{done.stderr}"
        )
    return done.stdout


@pytest.mark.e2e
def test_given_built_wheels__when_a_generated_project_is_installed_clean__then_all_gates_pass(
    tmp_path: Path,
) -> None:
    """The v1 distribution acceptance gate.

    Deliberately does NOT put packages/arch-commons on sys.path: the whole
    point is to prove the built artifacts are self-sufficient. A generated
    project is installed from real wheels, in a clean venv, resolved with
    UV_FIND_LINKS + UV_NO_INDEX so nothing reaches a package index or the
    monorepo's source tree.
    """
    dist = tmp_path / "dist"
    _run(["uv", "build", "--out-dir", str(dist)], cwd=REPO)
    _run(["uv", "build", "--package", "arch-commons", "--out-dir", str(dist)], cwd=REPO)
    wheels = sorted(p.name for p in dist.glob("*.whl"))
    assert any(w.startswith("arch_standard-") for w in wheels), wheels
    assert any(w.startswith("arch_commons-") for w in wheels), wheels

    project = tmp_path / "acme"
    copier.run_copy(
        str(TEMPLATE_ROOT),
        str(project),
        data={"dependency_source": "index", "project_name": "Acme"},
        defaults=True,
        overwrite=True,
        unsafe=True,
        skip_tasks=True,
    )

    env = {
        **os.environ,
        "UV_FIND_LINKS": str(dist),
        # Resolve strictly from the locally built wheels.
        "UV_NO_INDEX": "1",
    }
    _run(["uv", "sync"], cwd=project, env=env)

    # The generated project's own gates.
    _run(["uv", "run", "ruff", "check", "."], cwd=project, env=env)
    _run(["uv", "run", "ruff", "format", "--check", "."], cwd=project, env=env)
    _run(["uv", "run", "mypy"], cwd=project, env=env)
    _run(["uv", "run", "pytest"], cwd=project, env=env)

    # The standard, running from the installed wheel, against the generated project.
    _run(["uv", "run", "arch-standard", "render-importlinter", "."], cwd=project, env=env)
    core = _run(["uv", "run", "arch-standard", "check", "--core", "."], cwd=project, env=env)
    assert "0 failed" in core
    assert "0 errored" in core

    # Warnings are permitted here (e.g. the parked ARCH-019 example warning) --
    # only failures and errors are asserted against.
    full = _run(["uv", "run", "arch-standard", "check", "."], cwd=project, env=env)
    assert "0 failed" in full
    assert "0 errored" in full

    # The installed wheel carries its own catalog.
    count = _run(
        [
            "uv",
            "run",
            "python",
            "-c",
            "from arch_standard.rules.catalog import Catalog, packaged_rules_dir;"
            "print(len(Catalog.load(packaged_rules_dir())))",
        ],
        cwd=project,
        env=env,
    )
    assert count.strip().endswith("53")

    _run(["uv", "build"], cwd=project, env=env)
