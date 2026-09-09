from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_STAMP_FILENAME = ".arch-standard"


class StampError(Exception):
    """The .arch-standard stamp exists but cannot be interpreted."""


@dataclass(frozen=True)
class VersionStamp:
    standard_version: str
    template_version: str


def read_stamp(root: Path) -> VersionStamp | None:
    path = root / _STAMP_FILENAME
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise StampError(f"{path} is not valid TOML: {exc}") from exc
    values: dict[str, str] = {}
    for key in ("standard-version", "template-version"):
        if key not in data:
            raise StampError(f"{path} is missing required key {key!r}")
        value = data[key]
        if not isinstance(value, str):
            raise StampError(f"{path}: {key} must be a string, got {type(value).__name__}")
        try:
            parse_semver(value)
        except ValueError as exc:
            raise StampError(f"{path}: {key} is not a valid version: {value!r}") from exc
        values[key] = value
    return VersionStamp(
        standard_version=values["standard-version"],
        template_version=values["template-version"],
    )


def parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"expected MAJOR.MINOR.PATCH, got {version!r}")
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"expected numeric version parts, got {version!r}") from exc
    return major, minor, patch


def majors_crossed(stamp_version: str, running_version: str) -> list[int]:
    """Every major version boundary strictly between the stamp and the
    running catalog, inclusive of the running major. Empty when the project
    is current or ahead."""
    stamp_major = parse_semver(stamp_version)[0]
    running_major = parse_semver(running_version)[0]
    if running_major <= stamp_major:
        return []
    return list(range(stamp_major + 1, running_major + 1))
