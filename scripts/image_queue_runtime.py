"""Resumable queue persistence and retry policy."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def now() -> datetime:
    return datetime.now(timezone.utc)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict[str, Any]) -> None:
    data["updated_at"] = now().isoformat()
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def eligible(task: dict[str, Any]) -> bool:
    if task["status"] == "pending":
        return True
    if task["status"] == "running":
        started = task.get("started_at")
        return bool(started and datetime.fromisoformat(started) <= now() - timedelta(minutes=30))
    if task["status"] != "failed" or task["attempt_count"] >= task["max_attempts"]:
        return False
    retry = task.get("next_retry_at")
    return not retry or datetime.fromisoformat(retry) <= now()


def mark_running(task: dict[str, Any], provider: str) -> None:
    task.update({"status": "running", "provider": provider, "attempt_count": task["attempt_count"] + 1, "started_at": now().isoformat(), "last_error": None, "last_error_type": None})


def mark_failure(task: dict[str, Any], error_type: str, message: str, retryable: bool) -> None:
    exhausted = task["attempt_count"] >= task["max_attempts"]
    status = "blocked" if exhausted or not retryable else "failed"
    delay_minutes = min(2 ** max(task["attempt_count"] - 1, 0), 15)
    task.update({"status": status, "last_error_type": error_type, "last_error": message, "next_retry_at": (now() + timedelta(minutes=delay_minutes)).isoformat() if status == "failed" else None})


def mark_success(task: dict[str, Any], source: Path, canonical: str) -> None:
    task.update({"status": "succeeded", "source_image_path": source.as_posix(), "canonical_path": canonical, "completed_at": now().isoformat(), "next_retry_at": None})
