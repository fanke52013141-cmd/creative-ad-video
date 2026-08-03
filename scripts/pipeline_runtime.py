"""Config-driven production state and gate helpers."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_runtime import (
    verify_artifact_approval, verify_storyboard_text_approval,
    verify_stage_approvals, verify_stage_integrity,
)
from pipeline_spec import load_pipeline_spec, stage_map, stage_rows

SPEC = load_pipeline_spec()
STAGE_ROWS = stage_rows()
STAGE_MAP = stage_map()
STAGES = [row["id"] for row in STAGE_ROWS]
PREREQUISITES = {row["id"]: row["depends_on"] for row in STAGE_ROWS}
APPROVAL_REQUIRED = {row["id"] for row in STAGE_ROWS if row["approval_required"]}
SKIPPABLE = {row["id"] for row in STAGE_ROWS if row.get("allow_skip")}
TERMINAL_OK = {"approved", "completed", "skipped"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_checkpoint(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "checkpoint.json"
    data = read_json(path)
    if data.get("schema_version") != SPEC["schema_version"]:
        raise ValueError(f"checkpoint schema {data.get('schema_version')} does not match pipeline {SPEC['schema_version']}; migrate the run")
    if data.get("phase_order") != STAGES or set(data.get("stages", {})) != set(STAGES):
        raise ValueError("checkpoint stages do not match PipelineSpec; migrate the run")
    data.setdefault("blockers", [])
    return data


def save_checkpoint(run_dir: Path, data: dict[str, Any]) -> None:
    data["last_updated"] = now()
    write_json(run_dir / "checkpoint.json", data)


def gate_errors(run_dir: Path, checkpoint: dict[str, Any], target_stage: str) -> list[str]:
    if target_stage not in STAGE_MAP:
        return [f"unknown stage: {target_stage}"]
    errors = []
    for dependency in PREREQUISITES[target_stage]:
        status = checkpoint["stages"][dependency]["status"]
        if status not in TERMINAL_OK:
            errors.append(f"{dependency} is {status}, expected approved/completed/skipped")
            continue
        errors.extend(verify_stage_integrity(run_dir, checkpoint, dependency))
        if dependency in APPROVAL_REQUIRED and status == "approved":
            errors.extend(verify_stage_approvals(run_dir, checkpoint, dependency))
    if target_stage == "final_package":
        skipped = [
            name for name, row in checkpoint["stages"].items()
            if row.get("status") == "skipped" and row.get("skip_effect") == "draft_only"
        ]
        if skipped:
            errors.append("final package requires fulfilled production media; draft-only stages skipped: " + ", ".join(skipped))
        try:
            asset_plan = read_json(run_dir / "outputs" / "asset_manifest.json")
            asset_results = read_json(run_dir / "outputs" / "asset_media_manifest.json")["media"]
            board_plan = read_json(run_dir / "outputs" / "storyboard_board_manifest.json")
            board_results = read_json(run_dir / "outputs" / "storyboard_media_manifest.json")["media"]
            latest_assets = {}
            for row in asset_results:
                if row["asset_id"] not in latest_assets or row["revision"] > latest_assets[row["asset_id"]]["revision"]:
                    latest_assets[row["asset_id"]] = row
            latest_boards = {}
            for row in board_results:
                if row["board_id"] not in latest_boards or row["revision"] > latest_boards[row["board_id"]]["revision"]:
                    latest_boards[row["board_id"]] = row
            for item in (item for group in ("characters", "scenes", "props") for item in asset_plan.get(group, []) if item.get("generation_required")):
                media = latest_assets.get(item["asset_id"])
                if not media:
                    errors.append(f"final package missing asset media: {item['asset_id']}")
                else:
                    errors.extend(verify_artifact_approval(run_dir, media["media_revision_id"]))
            for board in board_plan["boards"]:
                media = latest_boards.get(board["board_id"])
                if not media:
                    errors.append(f"final package missing storyboard media: {board['board_id']}")
                else:
                    required_text = [item["content"] for item in board["required_text"]]
                    errors.extend(verify_storyboard_text_approval(run_dir, media["media_revision_id"], required_text))
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"final package production manifest unavailable: {exc}")
    return errors


def ready_stages(run_dir: Path, checkpoint: dict[str, Any]) -> list[str]:
    return [
        stage for stage in STAGES
        if checkpoint["stages"][stage]["status"] in {"not_started", "failed", "blocked", "invalidated"}
        and not gate_errors(run_dir, checkpoint, stage)
    ]


def next_stage(checkpoint: dict[str, Any], run_dir: Path | None = None) -> str | None:
    if run_dir is not None:
        ready = ready_stages(run_dir, checkpoint)
        if ready:
            return ready[0]
    for stage in STAGES:
        if checkpoint["stages"][stage]["status"] not in TERMINAL_OK:
            return stage
    return None


def invalidate_from(checkpoint: dict[str, Any], stage: str, reason: str) -> list[str]:
    affected = {stage}
    changed = True
    while changed:
        changed = False
        for candidate, dependencies in PREREQUISITES.items():
            if candidate not in affected and any(dep in affected for dep in dependencies):
                affected.add(candidate)
                changed = True
    invalidated = []
    for name in STAGES:
        if name == stage or name not in affected:
            continue
        row = checkpoint["stages"][name]
        if row["status"] != "not_started":
            row.update({"status": "invalidated", "invalidated_by": stage, "invalidation_reason": reason, "updated_at": now()})
            invalidated.append(name)
    return invalidated
