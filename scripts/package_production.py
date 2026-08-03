#!/usr/bin/env python3
"""Build deterministic per-video packages from explicit manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from artifact_runtime import verify_artifact_approval, verify_storyboard_text_approval
from path_safety import relative_to_run, resolve_in_run

REPO_ROOT = Path(__file__).resolve().parents[1]


def read(path: Path, schema_name: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads((REPO_ROOT / "schemas" / schema_name).read_text(encoding="utf-8-sig"))
    errors = list(Draft202012Validator(schema).iter_errors(data))
    if errors:
        raise SystemExit(f"invalid {path.name}: {errors[0].message}")
    return data


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def copy_or_link(run: Path, source_rel: str, target: Path, mode: str) -> dict[str, Any]:
    source = resolve_in_run(run, source_rel, must_exist=True)
    row = {"source": relative_to_run(run, source), "sha256": digest(source), "size": source.stat().st_size}
    if mode == "portable":
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        row["package_path"] = relative_to_run(run, target)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-video production folders and final manifest.")
    parser.add_argument("run_dir")
    parser.add_argument("--mode", choices=["linked", "portable"], default="portable")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve(); outputs = run / "outputs"
    prompt_manifest = read(outputs / "video_prompt_manifest.json", "video_prompt_manifest.schema.json")
    board_manifest = read(outputs / "storyboard_board_manifest.json", "storyboard_board_manifest.schema.json")
    board_media_manifest = read(outputs / "storyboard_media_manifest.json", "storyboard_media_manifest.schema.json")
    assets = read(outputs / "asset_manifest.json", "asset_manifest.schema.json")
    asset_media_manifest = read(outputs / "asset_media_manifest.json", "asset_media_manifest.schema.json")
    boards = {row["board_id"]: row for row in board_manifest["boards"]}
    board_media = {}
    for row in board_media_manifest["media"]:
        if row["board_id"] not in board_media or row["revision"] > board_media[row["board_id"]]["revision"]:
            board_media[row["board_id"]] = row
    asset_groups = {group: {row["asset_name"]: row for row in assets.get(group, [])} for group in ("characters", "scenes", "props")}
    asset_media = {}
    for row in asset_media_manifest["media"]:
        if row["asset_id"] not in asset_media or row["revision"] > asset_media[row["asset_id"]]["revision"]:
            asset_media[row["asset_id"]] = row
    created_at = datetime.now(timezone.utc)
    package_id = created_at.strftime("PKG-%Y%m%dT%H%M%S%fZ")
    package_root = outputs / "final_packages" / package_id
    package_root.mkdir(parents=True, exist_ok=False)
    artifacts, blockers, all_files = [], [], []
    for video in prompt_manifest["videos"]:
        video_id = video["video_id"]
        folder = package_root / "videos" / video_id
        folder.mkdir(parents=True, exist_ok=True)
        references = []
        try:
            prompt_target = folder / "prompt.md"
            prompt_row = copy_or_link(run, video["prompt_path"], prompt_target, args.mode)
            if prompt_row["sha256"] != video["prompt_hash"]:
                blockers.append(f"{video_id}: video prompt hash mismatch")
            prompt_row.update({"role": "video_prompt", "id": video_id})
            references.append(prompt_row)
        except ValueError as exc:
            blockers.append(f"{video_id}: {exc}")
        for board_id in video["source_boards"]:
            board = boards.get(board_id)
            if not board or board["video_id"] != video_id:
                blockers.append(f"{video_id}: invalid board mapping {board_id}")
                continue
            media = board_media.get(board_id)
            if not media:
                blockers.append(f"{video_id}: storyboard media missing {board_id}")
                continue
            required_text = [item["content"] for item in board["required_text"]]
            approval_errors = verify_storyboard_text_approval(run, media["media_revision_id"], required_text)
            if approval_errors:
                blockers.extend(f"{video_id}: {error}" for error in approval_errors)
            try:
                row = copy_or_link(run, media["media_path"], folder / "references" / "boards" / f"{board_id}{Path(media['media_path']).suffix.lower()}", args.mode)
                row.update({"role": "storyboard_board", "id": board_id})
                references.append(row)
            except ValueError as exc:
                blockers.append(f"{video_id}: {exc}")
        reference_groups = (
            ("characters", "character_assets", "characters", "character"),
            ("props", "product_assets", "products", "product"),
        )
        for source_group, key, package_group, role in reference_groups:
            for name in video[key]:
                item = asset_groups[source_group].get(name)
                if not item:
                    blockers.append(f"{video_id}: unknown {role} asset {name}")
                    continue
                if role == "product" and item.get("business_role") != "advertised_product":
                    blockers.append(f"{video_id}: non-product prop cannot be a video reference: {name}")
                    continue
                if not item.get("generation_required"):
                    continue
                media = asset_media.get(item["asset_id"])
                if not media:
                    blockers.append(f"{video_id}: missing canonical image {name}")
                    continue
                approval_errors = verify_artifact_approval(run, media["media_revision_id"])
                if approval_errors:
                    blockers.extend(f"{video_id}: {error}" for error in approval_errors)
                try:
                    suffix = Path(media["media_path"]).suffix.lower()
                    row = copy_or_link(run, media["media_path"], folder / "references" / package_group / f"{item['asset_id']}{suffix}", args.mode)
                    row.update({"role": role, "id": item["asset_id"], "asset_name": name})
                    references.append(row)
                except ValueError as exc:
                    blockers.append(f"{video_id}: {exc}")
        segment = {
            "video_id": video_id,
            "source_shots": video["source_shots"],
            "source_boards": video["source_boards"],
            "duration_seconds": video["duration_seconds"],
            "aspect_ratio": video["aspect_ratio"],
            "package_mode": args.mode,
            "references": references,
        }
        segment_path = folder / "segment.json"
        segment_path.write_text(json.dumps(segment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        artifacts.append({
            "video_id": video_id,
            "folder": relative_to_run(run, folder),
            "mode": args.mode,
            "duration_seconds": video["duration_seconds"],
            "aspect_ratio": video["aspect_ratio"],
        })
    for path in sorted(x for x in package_root.rglob("*") if x.is_file()):
        all_files.append({"path": relative_to_run(run, path), "size": path.stat().st_size, "sha256": digest(path)})
    result = {
        "schema_version": "2.0",
        "package_id": package_id,
        "package_mode": args.mode,
        "package_root": relative_to_run(run, package_root),
        "status": "completed" if not blockers else "revise_required",
        "artifacts": {"video_segments": artifacts},
        "files": all_files,
        "quality_gates": {"completed_blockers_checked": True, "manifest_mapping_used": True},
        "known_gaps": [],
        "blocking_issues": blockers,
        "created_at": created_at.isoformat(),
    }
    manifest_path = outputs / "final_package_manifest.json"
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{result['status']}: {manifest_path}")
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
