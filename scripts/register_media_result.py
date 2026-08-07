#!/usr/bin/env python3
"""Import a generated asset or storyboard board image as an immutable versioned result.

Replaces the former import_generated_media.py (asset) and register_storyboard_result.py
(storyboard) with a single --kind driven entry point.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from artifact_runtime import latest_stage_revisions, register_media_artifact
from manifest_io import read_json, write_json
from path_safety import relative_to_run

_VALID_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def _find_asset(manifest: dict, subject_id: str):
    for group in ("characters", "scenes", "props"):
        for item in manifest.get(group, []):
            if item.get("asset_id") == subject_id:
                return item, group
    return None, None


def _build_target(run: Path, kind: str, subject_id: str, match, ext: str, version: int) -> Path:
    if kind == "asset":
        _, group_name = match
        safe_name = subject_id.replace(".", "_")
        return run / "outputs" / "assets" / group_name / "images" / f"{safe_name}.v{version:03d}{ext}"
    return run / "outputs" / "storyboard_boards" / f"{subject_id}.v{version:03d}{ext}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a generated or manually supplied image (asset or storyboard board).")
    parser.add_argument("run_dir")
    parser.add_argument("--kind", choices=["asset", "storyboard"], required=True)
    parser.add_argument("--id", required=True, help="asset_id (e.g. CH001) or board_id (e.g. SB001)")
    parser.add_argument("--source-file", required=True)
    args = parser.parse_args()

    run = Path(args.run_dir).resolve()
    source = Path(args.source_file).resolve()
    if not source.is_file() or source.suffix.lower() not in _VALID_EXT:
        raise SystemExit("Source must be an existing PNG, JPG, JPEG or WEBP image")

    kind = args.kind
    subject_id = args.id
    ext = source.suffix.lower()

    if kind == "asset":
        source_manifest = run / "outputs" / "asset_manifest.json"
        media_manifest = run / "outputs" / "asset_media_manifest.json"
        id_field = "asset_id"
        stage = "asset_image_generation"
        deps = ["asset_executor", "asset_prompt_generation"]
        artifact_name = f"asset-media.{subject_id}"
        manifest = read_json(source_manifest)
        match = _find_asset(manifest, subject_id)
        if match[0] is None:
            raise SystemExit(f"Unknown asset_id: {subject_id}")
    else:
        source_manifest = run / "outputs" / "storyboard_board_manifest.json"
        media_manifest = run / "outputs" / "storyboard_media_manifest.json"
        id_field = "board_id"
        stage = "storyboard_image_generation"
        deps = ["storyboard_prompt_generation"]
        artifact_name = f"storyboard-media.{subject_id}"
        manifest = read_json(source_manifest)
        match = next((row for row in manifest["boards"] if row["board_id"] == subject_id), None)
        if not match:
            raise SystemExit(f"Unknown board_id: {subject_id}")

    results = read_json(media_manifest) if media_manifest.is_file() else {"schema_version": "1.0", "media": []}
    previous = [row for row in results["media"] if row[id_field] == subject_id]
    next_version = max((row["revision"] for row in previous), default=0) + 1

    target = _build_target(run, kind, subject_id, match, ext, next_version)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(f"Refusing to overwrite versioned result: {target}")
    shutil.copy2(source, target)

    artifact = register_media_artifact(
        run,
        artifact_name=artifact_name,
        stage=stage,
        source=target,
        dependencies=latest_stage_revisions(run, deps),
    )
    results["media"].append({
        id_field: subject_id,
        "revision": next_version,
        "media_revision_id": artifact["artifact_revision_id"],
        "media_path": relative_to_run(run, target),
        "sha256": artifact["sha256"],
    })
    write_json(media_manifest, results)
    print(relative_to_run(run, target))


if __name__ == "__main__":
    main()
