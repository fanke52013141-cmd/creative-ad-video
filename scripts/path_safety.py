"""Confine model- and manifest-provided paths to a local run directory."""
from __future__ import annotations

from pathlib import Path


def resolve_in_run(run_dir: Path, value: str, *, must_exist: bool = False) -> Path:
    run = run_dir.resolve()
    candidate = Path(value)
    if candidate.is_absolute():
        raise ValueError(f"absolute paths are not allowed in run artifacts: {value}")
    target = (run / value.removeprefix("./")).resolve()
    try:
        target.relative_to(run)
    except ValueError as exc:
        raise ValueError(f"path escapes run directory: {value}") from exc
    if must_exist and not target.exists():
        raise ValueError(f"artifact path does not exist: {value}")
    return target


def relative_to_run(run_dir: Path, path: Path) -> str:
    return "./" + path.resolve().relative_to(run_dir.resolve()).as_posix()
