#!/usr/bin/env python3
"""One-way migration from mutable V6 manifests to immutable V7 contracts."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from artifact_runtime import (
    approve_artifact_revision, approve_stage_artifacts, digest_path,
    latest_stage_revisions, register_media_artifact, register_stage_artifacts,
)
from path_safety import relative_to_run, resolve_in_run
from pipeline_spec import load_pipeline_spec

MUTABLE_ASSET_FIELDS = {"canonical_path", "source_path", "content_hash", "version", "approval_status"}


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate a local run from V6 to V7.")
    parser.add_argument("run_dir")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve(); out = run / "outputs"
    checkpoint_path = run / "checkpoint.json"
    checkpoint = read(checkpoint_path)
    if checkpoint.get("schema_version") == "7.0":
        print("Run is already V7")
        return
    if checkpoint.get("schema_version") != "6.0":
        raise SystemExit(f"Unsupported checkpoint schema: {checkpoint.get('schema_version')}")

    asset_path = out / "asset_manifest.json"
    board_path = out / "storyboard_board_manifest.json"
    assets = read(asset_path)
    boards = read(board_path)
    pending_assets = []
    for group in ("characters", "scenes", "props"):
        for item in assets.get(group, []):
            if item.get("canonical_path"):
                pending_assets.append({
                    "asset_id": item["asset_id"], "media_path": item["canonical_path"],
                    "approved": item.get("approval_status") == "approved",
                })
            for key in MUTABLE_ASSET_FIELDS:
                item.pop(key, None)
    pending_boards = []
    for board in boards.get("boards", []):
        if board.get("image_path") and (run / board["image_path"].removeprefix("./")).is_file():
            pending_boards.append({
                "board_id": board["board_id"], "media_path": board["image_path"],
                "approved": board.get("approval_status") == "approved",
            })
        for key in ("image_path", "image_hash", "approval_status"):
            board.pop(key, None)
        prompt = resolve_in_run(run, board["prompt_path"], must_exist=True)
        board["prompt_hash"] = digest_path(prompt)

    prompt_rows = []
    for group in ("characters", "scenes", "props"):
        for item in assets.get(group, []):
            if not item.get("generation_required"):
                continue
            prompt = resolve_in_run(run, item["output_prompt_path"], must_exist=True)
            prompt_rows.append({"asset_id": item["asset_id"], "prompt_path": item["output_prompt_path"], "sha256": digest_path(prompt)})

    report = {
        "from": "6.0", "to": "7.0", "asset_media_candidates": len(pending_assets),
        "storyboard_media_candidates": len(pending_boards), "prompt_records": len(prompt_rows),
    }
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    for path in (checkpoint_path, asset_path, board_path, out / "artifact_registry.json", out / "approval_registry.json"):
        if path.is_file():
            backup = path.with_name(path.name + ".v6.bak")
            if backup.exists():
                raise SystemExit(f"Migration backup already exists: {backup}")
            shutil.copy2(path, backup)
    write(asset_path, assets)
    write(board_path, boards)
    write(out / "asset_prompt_manifest.json", {"schema_version": "1.0", "prompts": prompt_rows})
    write(out / "artifact_registry.json", {"schema_version": "1.0", "artifacts": []})
    write(out / "approval_registry.json", {"schema_version": "1.0", "approvals": []})

    spec = load_pipeline_spec(); stages = [row["id"] for row in spec["stages"]]
    old_stages = checkpoint.get("stages", {})
    checkpoint.update({"schema_version": "7.0", "phase_order": stages, "total_phases": len(stages)})
    checkpoint["stages"] = {stage: old_stages.get(stage, {"status": "not_started", "version": 0, "updated_at": None}) for stage in stages}
    for row in checkpoint["stages"].values():
        row.pop("artifact_revision_ids", None); row.pop("approval_ids", None)

    pre_media = ["idea_generation", "art_direction", "storyboard_director", "asset_executor", "asset_prompt_generation", "video_segment_planning", "storyboard_prompt_generation"]
    for stage in pre_media:
        row = checkpoint["stages"][stage]
        if row.get("status") not in {"completed", "approved", "review_required"}:
            continue
        revision_ids = register_stage_artifacts(run, checkpoint, stage)
        row["artifact_revision_ids"] = revision_ids
        if row.get("status") == "approved":
            row["approval_ids"] = approve_stage_artifacts(run, checkpoint, stage, "v6-to-v7-migration", "recreated from approved V6 stage")

    asset_media = []
    for candidate in pending_assets:
        source = resolve_in_run(run, candidate["media_path"], must_exist=True)
        artifact = register_media_artifact(run, artifact_name=f"asset-media.{candidate['asset_id']}", stage="asset_image_generation", source=source, dependencies=latest_stage_revisions(run, ["asset_executor", "asset_prompt_generation"]))
        asset_media.append({"asset_id": candidate["asset_id"], "revision": artifact["revision"], "media_revision_id": artifact["artifact_revision_id"], "media_path": relative_to_run(run, source), "sha256": artifact["sha256"]})
        if candidate["approved"]:
            approve_artifact_revision(run, artifact["artifact_revision_id"], "v6-to-v7-migration", "recreated from approved V6 media")
    write(out / "asset_media_manifest.json", {"schema_version": "1.0", "media": asset_media})

    board_media = []
    for candidate in pending_boards:
        source = resolve_in_run(run, candidate["media_path"], must_exist=True)
        artifact = register_media_artifact(run, artifact_name=f"storyboard-media.{candidate['board_id']}", stage="storyboard_image_generation", source=source, dependencies=latest_stage_revisions(run, ["storyboard_prompt_generation"]))
        board_media.append({"board_id": candidate["board_id"], "revision": artifact["revision"], "media_revision_id": artifact["artifact_revision_id"], "media_path": relative_to_run(run, source), "sha256": artifact["sha256"]})
        if candidate["approved"]:
            approve_artifact_revision(run, artifact["artifact_revision_id"], "v6-to-v7-migration", "recreated from approved V6 media")
    write(out / "storyboard_media_manifest.json", {"schema_version": "1.0", "media": board_media})

    for stage in ("asset_image_generation", "storyboard_image_generation", "video_prompt_generation"):
        row = checkpoint["stages"][stage]
        if row.get("status") == "completed":
            row["artifact_revision_ids"] = register_stage_artifacts(run, checkpoint, stage)
    checkpoint["stages"]["final_package"].update({"status": "invalidated", "invalidation_reason": "V7 packaging contract requires rebuild"})
    checkpoint["current_phase"] = next((stage for stage in stages if checkpoint["stages"][stage].get("status") not in {"approved", "completed", "skipped"}), "completed")
    checkpoint["completed_phases"] = [stage for stage in stages if checkpoint["stages"][stage].get("status") in {"approved", "completed", "skipped"}]
    write(checkpoint_path, checkpoint)
    write(out / "migration_report.json", report | {"status": "applied"})
    print(json.dumps(report | {"status": "applied"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
