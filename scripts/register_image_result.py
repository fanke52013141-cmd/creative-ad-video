#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

from image_queue_runtime import load, mark_failure, mark_success, save


def main() -> None:
    parser = argparse.ArgumentParser(description="Register one provider result and persist queue state immediately.")
    parser.add_argument("run_dir")
    parser.add_argument("task_id")
    parser.add_argument("--source-file")
    parser.add_argument("--error-type")
    parser.add_argument("--error")
    parser.add_argument("--retryable", action="store_true")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve(); queue_path = run / "outputs/image_generation_queue.json"
    data = load(queue_path)
    task = next((x for x in data["tasks"] if x["task_id"] == args.task_id), None)
    if not task:
        raise SystemExit(f"Unknown task: {args.task_id}")
    if task["status"] == "succeeded":
        raise SystemExit(f"Task already succeeded: {args.task_id}")
    if args.source_file:
        source = Path(args.source_file).resolve()
        command = [sys.executable, str(Path(__file__).with_name("import_generated_media.py")), str(run), task["asset_id"], str(source)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            mark_failure(task, "import_error", result.stderr or result.stdout, False)
            save(queue_path, data)
            raise SystemExit(result.stderr or result.stdout)
        canonical = result.stdout.strip().splitlines()[-1]
        mark_success(task, source, canonical)
    elif args.error_type and args.error:
        mark_failure(task, args.error_type, args.error, args.retryable)
    else:
        raise SystemExit("Provide --source-file or --error-type and --error")
    save(queue_path, data)
    print(f"{task['task_id']}: {task['status']}")


if __name__ == "__main__":
    main()
