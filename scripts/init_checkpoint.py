#!/usr/bin/env python3
"""Create a checkpoint whose stage structure is generated from PipelineSpec."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_spec import load_pipeline_spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a config-derived checkpoint.")
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    checkpoint = json.loads(Path(args.template).read_text(encoding="utf-8-sig"))
    checkpoint["project"].update({"slug": args.slug, "created_at": args.created_at, "run_dir": args.run_dir})
    checkpoint["last_updated"] = args.created_at
    spec = load_pipeline_spec()
    duration = spec["production_constraints"]["video_segment_duration_seconds"]
    production = checkpoint.setdefault("ad_production", {})
    production["aspect_ratio"] = production.get("aspect_ratio") or spec["production_defaults"]["video_aspect_ratio"]
    production.update({"min_clip_seconds": duration["minimum"], "max_clip_seconds": duration["maximum"]})
    stages = [row["id"] for row in spec["stages"]]
    checkpoint.update({
        "schema_version": spec["schema_version"],
        "current_phase": stages[0],
        "completed_phases": [],
        "phase_order": stages,
        "total_phases": len(stages),
        "stages": {stage: {"status": "not_started", "version": 0, "updated_at": None} for stage in stages},
    })
    target = Path(args.output)
    target.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
