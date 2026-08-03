#!/usr/bin/env python3
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = ("local_runs/", "outputs/")
FORBIDDEN_LEGACY_FILES = {
    "schemas/video_prompt.schema.json",
    "examples/minimal_run/outputs/video_prompts.json",
    "scripts/version_artifact.py",
    "scripts/resume_image_queue.py",
}
MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".wav"}
SECRET_PATTERNS = [re.compile(r"(?i)(api[_-]?key|token|password)\s*[:=]\s*['\"][^'\"]{8,}")]


def main() -> None:
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8").splitlines()
    errors = []
    for rel in tracked:
        normalized = rel.replace("\\", "/")
        if normalized in FORBIDDEN_LEGACY_FILES:
            errors.append(f"legacy contract tracked: {rel}")
        if normalized.startswith(FORBIDDEN_PREFIXES):
            errors.append(f"production path tracked: {rel}")
        path = ROOT / rel
        if path.suffix.lower() in MEDIA_SUFFIXES and not normalized.startswith("examples/"):
            errors.append(f"media outside examples tracked: {rel}")
        if path.is_file() and path.stat().st_size <= 2_000_000 and path.suffix.lower() in {".py", ".md", ".json", ".yaml", ".yml", ".env"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                errors.append(f"possible hard-coded secret: {rel}")
    if errors:
        print("\n".join("FAIL: " + x for x in errors)); raise SystemExit(1)
    print(f"OK: repository policy ({len(tracked)} tracked files)")


if __name__ == "__main__":
    main()
