"""Load and validate the single source of truth for pipeline behavior."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO_ROOT / "config" / "pipeline.yaml"
SPEC_SCHEMA = REPO_ROOT / "schemas" / "pipeline_spec.schema.json"


def _read_json(path: Path) -> dict[str, Any]:
    import json
    return json.loads(path.read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=4)
def load_pipeline_spec(path: str | None = None) -> dict[str, Any]:
    spec_path = Path(path).resolve() if path else DEFAULT_SPEC
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"pipeline spec root must be an object: {spec_path}")
    errors = sorted(Draft202012Validator(_read_json(SPEC_SCHEMA)).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{'.'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors)
        raise ValueError(f"invalid pipeline spec: {detail}")
    _validate_semantics(data)
    return data


def _validate_semantics(spec: dict[str, Any]) -> None:
    duration = spec["production_constraints"]["video_segment_duration_seconds"]
    if duration["minimum"] >= duration["maximum"]:
        raise ValueError("video segment minimum duration must be less than maximum")
    stages = spec["stages"]
    ids = [row["id"] for row in stages]
    if len(ids) != len(set(ids)):
        raise ValueError("pipeline stage ids must be unique")
    known = set(ids)
    position = {name: i for i, name in enumerate(ids)}
    used_slots = set()
    output_names, output_paths = [], []
    for row in stages:
        unknown = sorted(set(row["depends_on"]) - known)
        if unknown:
            raise ValueError(f"{row['id']} depends on unknown stages: {', '.join(unknown)}")
        later = [x for x in row["depends_on"] if position[x] >= position[row["id"]]]
        if later:
            raise ValueError(f"{row['id']} has non-acyclic dependencies: {', '.join(later)}")
        executor = row["executor"]
        if executor["type"] == "codex_skill" and not (executor.get("skill") or executor.get("slot")):
            raise ValueError(f"{row['id']} codex_skill executor requires skill or slot")
        if executor.get("slot") and executor["slot"] not in spec["strategy_slots"]:
            raise ValueError(f"{row['id']} references unknown strategy slot {executor['slot']}")
        if executor.get("slot"):
            used_slots.add(executor["slot"])
        if executor["type"] == "provider_or_manual" and not executor.get("skill"):
            raise ValueError(f"{row['id']} provider_or_manual executor requires skill")
        if executor["type"] == "script" and not executor.get("script"):
            raise ValueError(f"{row['id']} script executor requires script")
        if row.get("allow_skip") and row.get("skip_effect") != "draft_only":
            raise ValueError(f"{row['id']} skip policy must declare draft_only effect")
        output_names.extend(output["name"] for output in row["outputs"])
        output_paths.extend(output["path"] for output in row["outputs"])
    unused_slots = sorted(set(spec["strategy_slots"]) - used_slots)
    if unused_slots:
        raise ValueError("unused strategy slots: " + ", ".join(unused_slots))
    if len(output_names) != len(set(output_names)) or len(output_paths) != len(set(output_paths)):
        raise ValueError("pipeline output names and paths must be globally unique")


def stage_rows() -> list[dict[str, Any]]:
    return load_pipeline_spec()["stages"]


def stage_map() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in stage_rows()}


def resolve_stage_skill(stage: dict[str, Any], spec: dict[str, Any] | None = None) -> str | None:
    executor = stage["executor"]
    if executor.get("skill"):
        return executor["skill"]
    slot = executor.get("slot")
    if slot:
        return (spec or load_pipeline_spec())["strategy_slots"][slot]["default_skill"]
    return None


def resolve_skill_path(name: str, root: Path = REPO_ROOT) -> Path:
    path = root / ".agents" / "skills" / name / "SKILL.md"
    if not path.is_file():
        raise FileNotFoundError(f"skill not found: {name}")
    return path
