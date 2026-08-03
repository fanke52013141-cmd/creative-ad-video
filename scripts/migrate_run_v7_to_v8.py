#!/usr/bin/env python3
"""Migrate V7 runs to the V8 board-first video reference contract."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from artifact_runtime import digest_path, register_stage_artifacts
from path_safety import resolve_in_run
from pipeline_runtime import STAGES, invalidate_from
from pipeline_spec import load_pipeline_spec


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def backup(path: Path) -> None:
    if not path.is_file():
        return
    target = path.with_name(path.name + ".v7.bak")
    if target.exists():
        raise SystemExit(f"Migration backup already exists: {target}")
    shutil.copy2(path, target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate a local run from V7 to V8.")
    parser.add_argument("run_dir")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    run = Path(args.run_dir).resolve()
    out = run / "outputs"
    paths = {
        "checkpoint": run / "checkpoint.json",
        "storyboard": out / "storyboard.json",
        "assets": out / "asset_manifest.json",
        "segments": out / "video_segment_plan.json",
        "boards": out / "storyboard_board_manifest.json",
        "videos": out / "video_prompt_manifest.json",
        "artifacts": out / "artifact_registry.json",
        "approvals": out / "approval_registry.json",
        "final": out / "final_package_manifest.json",
    }
    checkpoint = read(paths["checkpoint"])
    if checkpoint.get("schema_version") == "8.0":
        print("Run is already V8")
        return
    if checkpoint.get("schema_version") != "7.0":
        raise SystemExit(f"Unsupported checkpoint schema: {checkpoint.get('schema_version')}")

    storyboard = read(paths["storyboard"])
    assets = read(paths["assets"])
    segments = read(paths["segments"])
    boards = read(paths["boards"])
    videos = read(paths["videos"])
    spec = load_pipeline_spec()
    bounds = spec["production_constraints"]["video_segment_duration_seconds"]
    aspect_ratio = checkpoint.get("ad_production", {}).get("aspect_ratio") or spec["production_defaults"]["video_aspect_ratio"]

    text_review_shots = []
    for shot in storyboard["shots"]:
        if "advertising_text" not in shot:
            shot["advertising_text"] = []
            text_review_shots.append(shot["shot_id"])

    product_review_props = []
    for prop in assets.get("props", []):
        if not prop.get("business_role"):
            prop["business_role"] = "story_prop"
            product_review_props.append(prop["asset_name"])

    invalid_segments = [
        row["video_id"] for row in segments["segments"]
        if not bounds["minimum"] <= row["duration_seconds"] <= bounds["maximum"]
    ]
    shots = {row["shot_id"]: row for row in storyboard["shots"]}
    for board in boards["boards"]:
        board_shots = [shots[shot_id] for shot_id in board["shot_ids"]]
        board["duration_seconds"] = sum(row["duration_seconds"] for row in board_shots)
        board["required_text"] = [
            {"shot_id": shot["shot_id"], **item}
            for shot in board_shots
            for item in shot["advertising_text"]
        ]
        prompt = resolve_in_run(run, board["prompt_path"], must_exist=True)
        board["prompt_hash"] = digest_path(prompt)
        packet_path = resolve_in_run(run, board["packet_path"], must_exist=True)
        packet = read(packet_path)
        packet["aspect_ratio"] = aspect_ratio
        packet["duration_seconds"] = board["duration_seconds"]
        packet["required_text"] = board["required_text"]
        for packet_shot in packet["shots"]:
            packet_shot["advertising_text"] = shots[packet_shot["shot_id"]]["advertising_text"]
        board["_packet"] = (packet_path, packet)
    boards["schema_version"] = "2.0"

    prop_by_name = {row["asset_name"]: row for row in assets.get("props", [])}
    for video in videos["videos"]:
        old_props = video.pop("prop_assets", [])
        video.pop("scene_assets", None)
        video["product_assets"] = sorted(
            name for name in old_props
            if prop_by_name.get(name, {}).get("business_role") == "advertised_product"
        )
        video["aspect_ratio"] = aspect_ratio
        prompt = resolve_in_run(run, video["prompt_path"], must_exist=True)
        video["prompt_hash"] = digest_path(prompt)
    videos["schema_version"] = "2.0"

    report = {
        "from": "7.0",
        "to": "8.0",
        "default_aspect_ratio": aspect_ratio,
        "text_contract_review_required": text_review_shots,
        "product_classification_review_required": product_review_props,
        "invalid_video_segments": invalid_segments,
        "regeneration_required": [
            "storyboard_director", "asset_executor", "storyboard_prompt_generation",
            "storyboard_image_generation", "video_prompt_generation", "final_package",
        ],
    }
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    for path in paths.values():
        backup(path)
    for board in boards["boards"]:
        packet_path, packet = board.pop("_packet")
        write(packet_path, packet)
    write(paths["storyboard"], storyboard)
    write(paths["assets"], assets)
    write(paths["boards"], boards)
    write(paths["videos"], videos)

    # Register V8 canonical revisions so historical V7 snapshots remain auditable
    # without being mistaken for the current canonical files.
    for stage in ("storyboard_director", "asset_executor", "storyboard_prompt_generation", "video_prompt_generation"):
        checkpoint["stages"][stage]["artifact_revision_ids"] = register_stage_artifacts(run, checkpoint, stage)

    checkpoint["schema_version"] = spec["schema_version"]
    checkpoint["phase_order"] = STAGES
    checkpoint["total_phases"] = len(STAGES)
    production = checkpoint.setdefault("ad_production", {})
    production.update({
        "aspect_ratio": aspect_ratio,
        "min_clip_seconds": bounds["minimum"],
        "max_clip_seconds": bounds["maximum"],
    })
    checkpoint["stages"]["storyboard_director"].update({
        "status": "invalidated",
        "invalidation_reason": "V8 requires explicit advertising_text review",
    })
    checkpoint["stages"]["storyboard_director"].pop("artifact_revision_ids", None)
    checkpoint["stages"]["storyboard_director"].pop("approval_ids", None)
    invalidate_from(checkpoint, "storyboard_director", "V8 board-first and advertising-text contract requires regeneration")
    for stage in STAGES[STAGES.index("asset_executor"):]:
        checkpoint["stages"][stage].pop("artifact_revision_ids", None)
        checkpoint["stages"][stage].pop("approval_ids", None)
    checkpoint["current_phase"] = "storyboard_director"
    checkpoint["completed_phases"] = [
        stage for stage in STAGES
        if checkpoint["stages"][stage].get("status") in {"approved", "completed", "skipped"}
    ]
    write(paths["checkpoint"], checkpoint)
    write(out / "migration_report.json", report | {"status": "applied"})
    print(json.dumps(report | {"status": "applied"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
