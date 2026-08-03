#!/usr/bin/env python3
"""Import a storyboard board image as an immutable versioned result."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from artifact_runtime import latest_stage_revisions, register_media_artifact
from path_safety import relative_to_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a generated or manually supplied storyboard board image.")
    parser.add_argument("run_dir")
    parser.add_argument("board_id")
    parser.add_argument("source_file")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve(); source = Path(args.source_file).resolve()
    if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise SystemExit("Source must be an existing PNG, JPG, JPEG or WEBP image")
    path = run / "outputs" / "storyboard_board_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    board = next((row for row in data["boards"] if row["board_id"] == args.board_id), None)
    if not board:
        raise SystemExit(f"Unknown board_id: {args.board_id}")
    result_path = run / "outputs" / "storyboard_media_manifest.json"
    results = json.loads(result_path.read_text(encoding="utf-8-sig")) if result_path.is_file() else {"schema_version": "1.0", "media": []}
    previous = [row for row in results["media"] if row["board_id"] == args.board_id]
    version = max((row["revision"] for row in previous), default=0) + 1
    target = run / "outputs" / "storyboard_boards" / f"{args.board_id}.v{version:03d}{source.suffix.lower()}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(f"Refusing to overwrite storyboard result: {target}")
    shutil.copy2(source, target)
    artifact = register_media_artifact(
        run,
        artifact_name=f"storyboard-media.{args.board_id}",
        stage="storyboard_image_generation",
        source=target,
        dependencies=latest_stage_revisions(run, ["storyboard_prompt_generation"]),
    )
    results["media"].append({
        "board_id": args.board_id,
        "revision": version,
        "media_revision_id": artifact["artifact_revision_id"],
        "media_path": relative_to_run(run, target),
        "sha256": artifact["sha256"],
    })
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relative_to_run(run, target))


if __name__ == "__main__":
    main()
