#!/usr/bin/env python3
"""Build deterministic V### prompt metadata from segment and board manifests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from artifact_runtime import digest_path
from path_safety import relative_to_run
from pipeline_spec import load_pipeline_spec


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build video prompt manifest.")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve(); out = run / "outputs"
    plan = read(out / "video_segment_plan.json")
    boards = read(out / "storyboard_board_manifest.json")["boards"]
    shot_map = {row["shot_id"]: row for row in read(out / "shot_asset_map.json")["shot_assets"]}
    assets = read(out / "asset_manifest.json")
    known_props = {row["asset_name"]: row for row in assets.get("props", [])}
    checkpoint = read(run / "checkpoint.json")
    default_aspect_ratio = load_pipeline_spec()["production_defaults"]["video_aspect_ratio"]
    aspect_ratio = checkpoint.get("ad_production", {}).get("aspect_ratio") or default_aspect_ratio
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
    target.write_text(json.dumps({"schema_version": "2.0", "videos": videos}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(videos)} video prompt records: {target}")


if __name__ == "__main__":
    main()
