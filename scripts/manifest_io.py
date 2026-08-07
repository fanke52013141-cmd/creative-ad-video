#!/usr/bin/env python3
"""Shared helpers for manifest read/write and aspect-ratio resolution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline_spec import load_pipeline_spec


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_aspect_ratio(checkpoint: dict[str, Any]) -> str:
    default = load_pipeline_spec()["production_defaults"]["video_aspect_ratio"]
    return checkpoint.get("ad_production", {}).get("aspect_ratio") or default
