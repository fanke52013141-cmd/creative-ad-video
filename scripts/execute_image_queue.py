#!/usr/bin/env python3
"""Prepare or consume one image task at a time through a provider-neutral queue."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from image_queue_runtime import eligible, load, mark_running, save

EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute/resume one image queue task safely.")
    parser.add_argument("run_dir")
    parser.add_argument("--provider", choices=["codex_builtin", "external_manual"], required=True)
    args = parser.parse_args()
    run = Path(args.run_dir).resolve(); queue_path = run / "outputs/image_generation_queue.json"
    queue = load(queue_path)
    task = None
    if args.provider == "external_manual":
        imports = run / "outputs/imports"
        task = next((x for x in queue["tasks"] if x["status"] == "waiting_for_provider" and x.get("provider") == args.provider and any((imports / f"{x['task_id']}{ext}").is_file() for ext in EXTENSIONS)), None)
    task = task or next((x for x in queue["tasks"] if eligible(x)), None)
    if not task:
        print("No eligible image tasks")
        return
    if task["status"] != "waiting_for_provider":
        mark_running(task, args.provider); save(queue_path, queue)
    prompt_path = run / task["prompt_path"].removeprefix("./")
    if args.provider == "codex_builtin":
        task["status"] = "waiting_for_provider"; save(queue_path, queue)
        print(json.dumps({"action": "call_builtin_image_tool", "task_id": task["task_id"], "prompt_path": str(prompt_path), "register_with": f"python scripts/register_image_result.py {run} {task['task_id']} --source-file <generated-file>"}, ensure_ascii=False, indent=2))
        return
    imports = run / "outputs/imports"
    source = next((imports / f"{task['task_id']}{ext}" for ext in EXTENSIONS if (imports / f"{task['task_id']}{ext}").is_file()), None)
    if not source:
        task["status"] = "waiting_for_provider"; save(queue_path, queue)
        print(f"Place the image at outputs/imports/{task['task_id']}.png (or jpg/jpeg/webp), then rerun")
        return
    command = [sys.executable, str(Path(__file__).with_name("register_image_result.py")), str(run), task["task_id"], "--source-file", str(source)]
    raise SystemExit(subprocess.run(command).returncode)


if __name__ == "__main__":
    main()
