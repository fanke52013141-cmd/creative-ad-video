#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path

from artifact_runtime import latest_stage_revisions, register_media_artifact
from path_safety import relative_to_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Import one generated asset into its canonical location.")
    parser.add_argument("run_dir")
    parser.add_argument("asset_id")
    parser.add_argument("source_file")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    source = Path(args.source_file).resolve()
    if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise SystemExit("Source must be an existing PNG, JPG, JPEG or WEBP image")
    manifest_path = run / "outputs/asset_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    match = None
    group_name = None
    for group in ("characters", "scenes", "props"):
        for item in data.get(group, []):
            if item.get("asset_id") == args.asset_id:
                match, group_name = item, group
    if not match:
        raise SystemExit(f"Unknown asset_id: {args.asset_id}")
    result_path = run / "outputs" / "asset_media_manifest.json"
    results = json.loads(result_path.read_text(encoding="utf-8-sig")) if result_path.is_file() else {"schema_version": "1.0", "media": []}
    previous = [row for row in results["media"] if row["asset_id"] == args.asset_id]
    next_version = max((row["revision"] for row in previous), default=0) + 1
    safe_name = match["asset_id"].replace(".", "_")
    target = run / "outputs" / "assets" / group_name / "images" / f"{safe_name}.v{next_version:03d}{source.suffix.lower()}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(f"Refusing to overwrite versioned asset: {target}")
    shutil.copy2(source, target)
    artifact = register_media_artifact(
        run,
        artifact_name=f"asset-media.{args.asset_id}",
        stage="asset_image_generation",
        source=target,
        dependencies=latest_stage_revisions(run, ["asset_executor", "asset_prompt_generation"]),
    )
    results["media"].append({
        "asset_id": args.asset_id,
        "revision": next_version,
        "media_revision_id": artifact["artifact_revision_id"],
        "media_path": relative_to_run(run, target),
        "sha256": artifact["sha256"],
    })
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relative_to_run(run, target))


if __name__ == "__main__":
    main()
