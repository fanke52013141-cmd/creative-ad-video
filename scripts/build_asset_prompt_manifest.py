#!/usr/bin/env python3
"""Build the immutable index of generated asset prompts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from artifact_runtime import digest_path
from path_safety import relative_to_run, resolve_in_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the asset prompt manifest.")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    plan_path = run / "outputs" / "asset_manifest.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    prompts = []
    for group in ("characters", "scenes", "props"):
        for item in plan.get(group, []):
            if not item.get("generation_required"):
                continue
            prompt_path = item.get("output_prompt_path")
            if not prompt_path:
                raise SystemExit(f"missing output_prompt_path: {item['asset_id']}")
            try:
                prompt = resolve_in_run(run, prompt_path, must_exist=True)
            except ValueError as exc:
                raise SystemExit(str(exc))
            prompts.append({
                "asset_id": item["asset_id"],
                "prompt_path": relative_to_run(run, prompt),
                "sha256": digest_path(prompt),
            })
    target = run / "outputs" / "asset_prompt_manifest.json"
    target.write_text(json.dumps({"schema_version": "1.0", "prompts": prompts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(prompts)} prompt records: {target}")


if __name__ == "__main__":
    main()
