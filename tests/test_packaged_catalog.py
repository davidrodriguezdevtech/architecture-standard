from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

from arch_standard.rules.catalog import Catalog, packaged_rules_dir


def test_given_the_installed_package__when_locating_rules__then_dir_is_inside_the_package() -> None:
    rules_dir = packaged_rules_dir()
    assert rules_dir.is_dir()
    assert rules_dir.name == "_catalog"
    assert (rules_dir / "structure.yaml").is_file()
    assert Path(Catalog.__module__.replace(".", "/")).name  # sanity: import path intact


def test_given_the_packaged_dir__when_loading__then_the_whole_catalog_loads() -> None:
    assert len(Catalog.load(packaged_rules_dir())) == 54


def test_given_a_built_wheel__when_installed_clean__then_it_ships_and_loads_the_catalog(
    tmp_path: Path,
) -> None:
    """The regression test for the v1 audit's headline finding."""
    repo = Path(__file__).resolve().parents[1]
    dist = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist)], cwd=repo, check=True, capture_output=True
    )
    wheels = list(dist.glob("arch_standard-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    python = env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "-q", str(wheels[0])], check=True)

    probe = (
        "from arch_standard.rules.catalog import Catalog, packaged_rules_dir; "
        "print(len(Catalog.load(packaged_rules_dir())))"
    )
    done = subprocess.run([str(python), "-c", probe], check=True, capture_output=True, text=True)
    assert done.stdout.strip() == "54"
