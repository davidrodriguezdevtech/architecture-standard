from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_STAMP_FILENAME = ".arch-standard"


@dataclass(frozen=True)
class VersionStamp:
    standard_version: str
    template_version: str


def read_stamp(root: Path) -> VersionStamp | None:
    path = root / _STAMP_FILENAME
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return VersionStamp(
        standard_version=data["standard-version"],
        template_version=data["template-version"],
    )


def parse_semver(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def majors_crossed(stamp_version: str, running_version: str) -> list[int]:
    """Every major version boundary strictly between the stamp and the
    running catalog, inclusive of the running major. Empty when the project
    is current or ahead."""
    stamp_major = parse_semver(stamp_version)[0]
    running_major = parse_semver(running_version)[0]
    if running_major <= stamp_major:
        return []
    return list(range(stamp_major + 1, running_major + 1))
