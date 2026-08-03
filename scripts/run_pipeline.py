#!/usr/bin/env python3
"""Stateful entrypoint for config-driven production stage control."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from artifact_runtime import approve_stage_artifacts, register_stage_artifacts, verify_stage_integrity
from pipeline_spec import REPO_ROOT
from pipeline_runtime import (
    APPROVAL_REQUIRED, PREREQUISITES, SKIPPABLE, STAGES, gate_errors, invalidate_from,
    load_checkpoint, next_stage, now, ready_stages, save_checkpoint,
)
from stage_gate import validate_stage_outputs


def add_blockers(checkpoint: dict, stage: str, errors: list[str]) -> None:
    checkpoint["blockers"] = [x for x in checkpoint.get("blockers", []) if x.get("stage") != stage]
    checkpoint["blockers"].extend({"stage": stage, "message": message, "created_at": now()} for message in errors)


def clear_blockers(checkpoint: dict, stage: str) -> None:
    checkpoint["blockers"] = [x for x in checkpoint.get("blockers", []) if x.get("stage") != stage]


def update_active_task(run: Path, checkpoint: dict, stage: str, status: str, revision_ids: list[str] | None = None) -> None:
    task_id = checkpoint["stages"][stage].get("active_task_id")
    if not task_id:
        return
    matches = list((run / "outputs" / "tasks" / stage).glob(f"{task_id}.json"))
    if not matches:
        return
    path = matches[0]
    task = json.loads(path.read_text(encoding="utf-8-sig"))
    task["status"] = status
    if revision_ids is not None:
        task["output_artifact_revisions"] = revision_ids
    schema = json.loads((REPO_ROOT / "schemas" / "stage_task.schema.json").read_text(encoding="utf-8-sig"))
    errors = list(Draft202012Validator(schema).iter_errors(task))
    if errors:
        raise ValueError(f"invalid active task update: {errors[0].message}")
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect and control the guarded production pipeline.")
    parser.add_argument("run_dir")
    parser.add_argument("action", choices=["status", "start", "complete", "approve", "reject", "invalidate", "skip"])
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--reason", default="")
    parser.add_argument("--actor", default="local-user")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    cp = load_checkpoint(run)
    stage = args.stage or next_stage(cp, run)
    if args.action == "status":
        print(json.dumps({"current_stage": next_stage(cp, run), "ready_stages": ready_stages(run, cp), "stages": cp["stages"], "blockers": cp["blockers"]}, ensure_ascii=False, indent=2))
        return
    if not stage:
        raise SystemExit("Pipeline already complete")
    row = cp["stages"][stage]
    if args.action == "start":
        integrity_blockers = []
        for dependency in PREREQUISITES[stage]:
            integrity_errors = verify_stage_integrity(run, cp, dependency)
            if integrity_errors:
                reason = "; ".join(integrity_errors)
                integrity_blockers.extend(integrity_errors)
                cp["stages"][dependency].update({"status": "invalidated", "invalidation_reason": reason, "updated_at": now()})
                invalidate_from(cp, dependency, reason)
        errors = integrity_blockers + gate_errors(run, cp, stage)
        if errors:
            add_blockers(cp, stage, errors); save_checkpoint(run, cp)
            raise SystemExit("BLOCKED:\n- " + "\n- ".join(errors))
        if row["status"] not in {"not_started", "failed", "blocked", "invalidated"}:
            raise SystemExit(f"Cannot start {stage} from {row['status']}")
        clear_blockers(cp, stage)
        row.update({"status": "in_progress", "started_at": now(), "updated_at": now()})
        update_active_task(run, cp, stage, "dispatched")
    elif args.action == "complete":
        if row["status"] != "in_progress":
            raise SystemExit(f"Cannot complete {stage} from {row['status']}")
        try:
            validate_stage_outputs(run, stage)
            revision_ids = register_stage_artifacts(run, cp, stage)
        except (ValueError, KeyError) as exc:
            add_blockers(cp, stage, [str(exc)]); save_checkpoint(run, cp)
            raise SystemExit(f"BLOCKED: {exc}")
        row.update({"status": "review_required" if stage in APPROVAL_REQUIRED else "completed", "version": row.get("version", 0) + 1, "artifact_revision_ids": revision_ids, "updated_at": now()})
        update_active_task(run, cp, stage, "completed", revision_ids)
        clear_blockers(cp, stage)
    elif args.action == "approve":
        if stage not in APPROVAL_REQUIRED or row["status"] != "review_required":
            raise SystemExit(f"Cannot approve {stage} from {row['status']}")
        try:
            validate_stage_outputs(run, stage, approving=True)
            approval_ids = approve_stage_artifacts(run, cp, stage, args.actor, args.reason)
        except ValueError as exc:
            add_blockers(cp, stage, [str(exc)]); save_checkpoint(run, cp)
            raise SystemExit(f"BLOCKED: {exc}")
        row.update({"status": "approved", "approval_ids": approval_ids, "approved_at": now(), "updated_at": now()})
        clear_blockers(cp, stage)
    elif args.action == "reject":
        if row["status"] not in {"review_required", "in_progress"}:
            raise SystemExit(f"Cannot reject {stage} from {row['status']}")
        reason = args.reason or "rejected"
        row.update({"status": "failed", "failure_reason": reason, "updated_at": now()})
        update_active_task(run, cp, stage, "failed")
        add_blockers(cp, stage, [reason])
    elif args.action == "skip":
        if stage not in SKIPPABLE or row["status"] not in {"not_started", "in_progress", "blocked"}:
            raise SystemExit(f"Cannot skip {stage} from {row['status']}")
        if not args.reason:
            raise SystemExit("Skipping requires --reason")
        row.update({"status": "skipped", "skip_reason": args.reason, "skip_effect": "draft_only", "updated_at": now()})
        update_active_task(run, cp, stage, "skipped")
        clear_blockers(cp, stage)
    elif args.action == "invalidate":
        invalidated = invalidate_from(cp, stage, args.reason or "upstream artifact changed")
        row.update({"status": "invalidated", "updated_at": now()})
        update_active_task(run, cp, stage, "invalidated")
        print("Invalidated: " + ", ".join(invalidated))
    cp["current_phase"] = next_stage(cp, run) or "completed"
    cp["completed_phases"] = [s for s in STAGES if cp["stages"][s]["status"] in {"approved", "completed", "skipped"}]
    save_checkpoint(run, cp)
    print(f"{stage}: {row['status']}")


if __name__ == "__main__":
    main()
