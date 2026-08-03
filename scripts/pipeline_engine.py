#!/usr/bin/env python3
"""Materialize ready DAG nodes and execute deterministic stage handlers."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from pipeline_runtime import load_checkpoint, ready_stages, save_checkpoint
from pipeline_spec import REPO_ROOT, load_pipeline_spec, resolve_skill_path, resolve_stage_skill, stage_map


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def materialize_task(run: Path, stage: str) -> tuple[Path, dict]:
    cp = load_checkpoint(run); spec = load_pipeline_spec(); row = stage_map()[stage]
    tasks_root = run / "outputs" / "tasks"
    existing = list(tasks_root.rglob("TASK-*.json")) if tasks_root.is_dir() else []
    task_id = f"TASK-{len(existing) + 1:06d}"
    dependencies = []
    for name in row["depends_on"]:
        dependencies.extend(cp["stages"][name].get("artifact_revision_ids", []))
    dependencies = sorted(set(dependencies))
    stage_root = tasks_root / stage
    if stage_root.is_dir():
        for candidate in sorted(stage_root.glob("TASK-*.json"), reverse=True):
            payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
            if payload.get("status") in {"ready", "dispatched"} and payload.get("dependency_artifacts") == dependencies:
                cp["stages"][stage]["active_task_id"] = payload["task_id"]
                save_checkpoint(run, cp)
                return candidate, payload
    executor = dict(row["executor"])
    skill = resolve_stage_skill(row, spec)
    if skill:
        executor["resolved_skill"] = skill
        executor["resolved_skill_path"] = resolve_skill_path(skill).relative_to(REPO_ROOT).as_posix()
    payload = {
        "schema_version": "1.0",
        "pipeline_schema_version": spec["schema_version"],
        "task_id": task_id,
        "stage": stage,
        "executor": executor,
        "dependency_artifacts": dependencies,
        "expected_outputs": row.get("outputs", []),
        "status": "ready",
        "created_at": now(),
    }
    target = tasks_root / stage / f"{task_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = json.loads((REPO_ROOT / "schemas" / "stage_task.schema.json").read_text(encoding="utf-8-sig"))
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise ValueError(f"invalid stage task: {errors[0].message}")
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cp["stages"][stage]["active_task_id"] = task_id
    save_checkpoint(run, cp)
    return target, payload


def pipeline_command(run: Path, action: str, stage: str, *extra: str) -> int:
    command = [sys.executable, str(Path(__file__).with_name("run_pipeline.py")), str(run), action, "--stage", stage, *extra]
    return subprocess.run(command).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize or execute ready pipeline nodes.")
    parser.add_argument("run_dir")
    parser.add_argument("action", choices=["ready", "materialize", "run"])
    parser.add_argument("--stage")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve(); cp = load_checkpoint(run)
    ready = ready_stages(run, cp)
    if args.action == "ready":
        print(json.dumps({"ready_stages": ready}, ensure_ascii=False, indent=2)); return
    stage = args.stage or (ready[0] if ready else None)
    if not stage or stage not in ready:
        raise SystemExit(f"stage is not ready: {stage}")
    task_path, task = materialize_task(run, stage)
    if args.action == "materialize":
        print(task_path); return
    if pipeline_command(run, "start", stage):
        raise SystemExit(1)
    executor = task["executor"]
    if executor["type"] != "script":
        task["status"] = "dispatched"
        task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"action": "execute_stage_task", "task_path": str(task_path), "executor": executor, "complete_with": f"python scripts/run_pipeline.py {run} complete --stage {stage}"}, ensure_ascii=False, indent=2))
        return
    script = Path(__file__).resolve().parents[1] / executor["script"]
    command = [sys.executable, str(script), str(run)]
    result = subprocess.run(command)
    if result.returncode:
        pipeline_command(run, "reject", stage, "--reason", f"executor failed with exit {result.returncode}")
        task["status"] = "failed"
    else:
        task["status"] = "completed"
        if pipeline_command(run, "complete", stage):
            task["status"] = "failed"
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if task["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
