#!/usr/bin/env python3
"""Reject documentation references to repository paths that do not exist."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ("scripts/", "schemas/", "docs/", ".agents/", "skills/", "config/", "checks/", "bad_cases/", "inputs/", "examples/")


def main() -> None:
    documents = [
        ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "PIPELINE_FLOW.md",
        *(ROOT / "docs").rglob("*.md"), *(ROOT / "checks").rglob("*.md"),
        *(ROOT / ".agents" / "skills").rglob("SKILL.md"),
    ]
    missing = []
    for document in documents:
        for value in re.findall(r"`([^`]+)`", document.read_text(encoding="utf-8-sig")):
            value = value.strip().replace("\\", "/")
            if not value.startswith(PREFIXES) or any(token in value for token in ("*", "<", ">", "|", " ")):
                continue
            if not (ROOT / value).exists():
                missing.append(f"{document.relative_to(ROOT)}: {value}")
    if missing:
        print("\n".join("FAIL: missing reference: " + row for row in missing))
        raise SystemExit(1)
    print(f"OK: document references ({len(documents)} files)")


if __name__ == "__main__":
    main()
