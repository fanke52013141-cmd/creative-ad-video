#!/usr/bin/env python3
"""Build deterministic V### prompt metadata from segment and board manifests."""
from __future__ import annotations

import argparse
from pathlib import Path

from artifact_runtime import digest_path
from manifest_io import read_json, write_json, resolve_aspect_ratio
from path_safety import relative_to_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Build video prompt manifest.")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve(); out = run / "outputs"
    plan = read_json(out / "video_segment_plan.json")
    boards = read_json(out / "storyboard_board_manifest.json")["boards"]
    shot_map = {row["shot_id"]: row for row in read_json(out / "shot_asset_map.json")["shot_assets"]}
    assets = read_json(out / "asset_manifest.json")
    known_props = {row["asset_name"]: row for row in assets.get("props", [])}
    checkpoint = read_json(run / "checkpoint.json")
    aspect_ratio = resolve_aspect_ratio(checkpoint)
    videos = []
    for segment in plan["segments"]:
        video_id = segment["video_id"]
        source_boards = [row["board_id"] for row in boards if row["video_id"] == video_id]
        if not source_boards:
            raise SystemExit(f"no storyboard boards mapped to {video_id}")
        character_assets: set[str] = set()
        product_assets: set[str] = set()
        for shot_id in segment["source_shots"]:
            mapping = shot_map[shot_id]
            character_assets.update(mapping["characters"])
            for prop_name in mapping["props"]:
                prop = known_props.get(prop_name)
                if not prop:
                    raise SystemExit(f"unknown prop in shot asset map: {prop_name}")
                if prop.get("business_role") == "advertised_product":
                    product_assets.add(prop_name)
        prompt = out / "video_prompts" / f"{video_id}.md"
        if not prompt.is_file():
            raise SystemExit(f"missing video prompt: {prompt}")
        videos.append({
            "video_id": video_id,
            "source_shots": segment["source_shots"],
            "source_boards": source_boards,
            "duration_seconds": segment["duration_seconds"],
            "aspect_ratio": aspect_ratio,
            "prompt_path": relative_to_run(run, prompt),
            "prompt_hash": digest_path(prompt),
            "character_assets": sorted(character_assets),
            "product_assets": sorted(product_assets),
        })
    target = out / "video_prompt_manifest.json"
    write_json(target, {"schema_version": "2.0", "videos": videos})
    print(f"Wrote {len(videos)} video prompt records: {target}")


if __name__ == "__main__":
    main()
