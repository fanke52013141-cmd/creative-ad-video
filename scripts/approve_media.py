#!/usr/bin/env python3
"""Approve a generated asset or storyboard image and bind the decision to its hash."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from artifact_runtime import approve_artifact_revision, verify_artifact_approval


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve one media result.")
    parser.add_argument("run_dir")
    parser.add_argument("kind", choices=["asset", "board"])
    parser.add_argument("target_id")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--comment", default="")
    parser.add_argument("--verified-text", action="append", default=[], help="Exact advertising text seen in the board; repeat for multiple items.")
    parser.add_argument("--confirm-no-extra-text", action="store_true", help="Confirm that no undeclared text appears in the board.")
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    evidence = None
    if args.kind == "asset":
        path = run / "outputs" / "asset_media_manifest.json"
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        matches = [row for row in data["media"] if row["asset_id"] == args.target_id]
        if not matches:
            raise SystemExit(f"Asset result not registered: {args.target_id}")
        revision_id = max(matches, key=lambda row: row["revision"])["media_revision_id"]
    else:
        path = run / "outputs" / "storyboard_media_manifest.json"
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        matches = [row for row in data["media"] if row["board_id"] == args.target_id]
        if not matches:
            raise SystemExit(f"Unknown board: {args.target_id}")
        revision_id = max(matches, key=lambda row: row["revision"])["media_revision_id"]
        board_plan_path = run / "outputs" / "storyboard_board_manifest.json"
        board_plan = json.loads(board_plan_path.read_text(encoding="utf-8-sig"))
        board = next((row for row in board_plan["boards"] if row["board_id"] == args.target_id), None)
        if not board:
            raise SystemExit(f"Unknown board plan: {args.target_id}")
        declared_text = [item["content"] for item in board["required_text"]]
        if args.verified_text != declared_text:
            raise SystemExit(
                f"Storyboard text mismatch for {args.target_id}: expected {declared_text!r}, got {args.verified_text!r}"
            )
        if not args.confirm_no_extra_text:
            raise SystemExit("Board approval requires --confirm-no-extra-text")
        evidence = {
            "text_verification": {
                "declared_text": declared_text,
                "verified_text": args.verified_text,
                "exact_match": True,
                "extra_text_absent": True,
            }
        }
    if args.kind == "asset" and (args.verified_text or args.confirm_no_extra_text):
        raise SystemExit("Text verification flags are only valid for board approvals")
    try:
        approval_id = approve_artifact_revision(
            run, revision_id, args.actor, args.comment,
            evidence=evidence,
        )
    except ValueError as exc:
        raise SystemExit(str(exc))
    errors = verify_artifact_approval(run, revision_id)
    if errors:
        raise SystemExit("; ".join(errors))
    print(f"{args.kind} {args.target_id}: approved ({approval_id})")


if __name__ == "__main__":
    main()
