#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from path_safety import resolve_in_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic asset image queue.")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    manifest_path = run / "outputs/asset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out = run / "outputs/image_generation_queue.json"
    previous = {}
    if out.is_file():
        previous = {x["asset_id"]: x for x in json.loads(out.read_text(encoding="utf-8")).get("tasks", [])}
    tasks = []
    for group in ("characters", "scenes", "props"):
        for item in manifest.get(group, []):
            if not item.get("generation_required"):
                continue
            prompt = item.get("output_prompt_path")
            if not prompt:
                raise SystemExit(f"Missing output_prompt_path: {item.get('asset_name')}")
            try:
                resolve_in_run(run, prompt, must_exist=True)
            except ValueError as exc:
                raise SystemExit(str(exc))
            stable = previous.get(item["asset_id"], {})
            tasks.append({
                "task_id": f"IMG-{len(tasks)+1:04d}",
                "asset_id": item["asset_id"],
                "asset_type": item["asset_type"],
                "asset_name": item["asset_name"],
                "prompt_path": prompt,
                "status": stable.get("status", "pending"),
                "provider": stable.get("provider"),
                "attempt_count": stable.get("attempt_count", 0),
                "max_attempts": stable.get("max_attempts", 3),
                "last_error_type": stable.get("last_error_type"),
                "last_error": stable.get("last_error"),
                "source_image_path": stable.get("source_image_path"),
                "canonical_path": stable.get("canonical_path"),
                "started_at": stable.get("started_at"),
                "completed_at": stable.get("completed_at"),
                "next_retry_at": stable.get("next_retry_at")
            })
    payload = {"schema_version": "1.0", "updated_at": datetime.now(timezone.utc).isoformat(), "tasks": tasks}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(tasks)} tasks: {out}")


if __name__ == "__main__":
    main()
