#!/usr/bin/env python3
"""Deterministically map V### segments to SB### boards and materialize AI packets."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from manifest_io import read_json, write_json, resolve_aspect_ratio
from path_safety import relative_to_run


def sha256(path: Path) -> str | None:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def chunks(values: list[str], size: int = 4) -> list[list[str]]:
    return [values[i:i + size] for i in range(0, len(values), size)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build board packets and the V/SB/S manifest.")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    out = run / "outputs"
    storyboard = read_json(out / "storyboard.json")
    shot_map = read_json(out / "shot_asset_map.json")
    assets = read_json(out / "asset_manifest.json")
    plan = read_json(out / "video_segment_plan.json")
    checkpoint = read_json(run / "checkpoint.json")
    aspect_ratio = resolve_aspect_ratio(checkpoint)
    shots = {row["shot_id"]: row for row in storyboard["shots"]}
    mapped = {row["shot_id"]: row for row in shot_map["shot_assets"]}
    prop_details = {row["asset_name"]: row for row in assets.get("props", [])}
    manifest_path = out / "storyboard_board_manifest.json"
    boards = []
    board_number = 0
    for segment in plan["segments"]:
        for shot_ids in chunks(segment["source_shots"]):
            board_number += 1
            board_id = f"SB{board_number:03d}"
            packet_shots = []
            frame_roles = {row["shot_id"]: row["role"] for row in segment["frame_plan"]}
            for shot_id in shot_ids:
                if shot_id not in shots or shot_id not in mapped:
                    raise SystemExit(f"missing storyboard or asset-map row: {shot_id}")
                shot = shots[shot_id]
                mapping = mapped[shot_id]
                advertising_text = [dict(item) for item in shot.get("advertising_text", [])]
                packet_shots.append({
                    "shot_id": shot_id,
                    "role": frame_roles[shot_id],
                    "framing": shot["framing"],
                    "camera_move": shot["camera_move"],
                    "action_desc": shot["action_desc"],
                    "advertising_text": advertising_text,
                    "assets": {
                        "characters": mapping["characters"],
                        "scenes": mapping["scenes"],
                        "key_props": [
                            {
                                "name": name,
                                "is_key_item": True,
                                "business_role": prop_details[name].get("business_role"),
                                "recurrence_count": prop_details[name].get("recurrence_count", 0),
                            }
                            for name in mapping["props"] if prop_details.get(name, {}).get("is_key_item")
                        ],
                    },
                })
            required_text = [
                {"shot_id": shot["shot_id"], **item}
                for shot in packet_shots
                for item in shot["advertising_text"]
            ]
            board_duration = sum(shots[x]["duration_seconds"] for x in shot_ids)
            packet = {
                "board_id": board_id,
                "video_id": segment["video_id"],
                "scene_id": segment["scene_id"],
                "duration_seconds": board_duration,
                "aspect_ratio": aspect_ratio,
                "required_text": required_text,
                "shots": packet_shots,
            }
            packet_path = out / "storyboard_board_inputs" / f"{board_id}.json"
            write_json(packet_path, packet)
            prompt_path = out / "storyboard_boards" / f"{board_id}.md"
            boards.append({
                "board_id": board_id,
                "video_id": segment["video_id"],
                "shot_ids": shot_ids,
                "duration_seconds": board_duration,
                "required_text": required_text,
                "packet_path": relative_to_run(run, packet_path),
                "prompt_path": relative_to_run(run, prompt_path),
                "prompt_hash": sha256(prompt_path),
            })
    payload = {"schema_version": "2.0", "boards": boards}
    write_json(manifest_path, payload)
    print(f"Wrote {len(boards)} board packets and {manifest_path}")


if __name__ == "__main__":
    main()
