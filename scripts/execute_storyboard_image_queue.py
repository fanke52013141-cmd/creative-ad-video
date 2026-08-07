#!/usr/bin/env python3
"""Return exactly one storyboard board that still needs an image, enforcing one-board-one-image.

This mirrors execute_image_queue.py for the storyboard branch so the fulfillment
agent is handed a single SB### prompt at a time and can never be tempted to read
the whole storyboard_board_manifest.json and merge multiple boards into one image.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit one eligible storyboard board task at a time.")
    parser.add_argument("run_dir")
    parser.add_argument("--provider", choices=["codex_builtin", "external_manual"], required=True)
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    manifest_path = run / "outputs/storyboard_board_manifest.json"
    manifest = read_json(manifest_path)
    media_path = run / "outputs/storyboard_media_manifest.json"
    done = set()
    if media_path.is_file():
        done = {row["board_id"] for row in read_json(media_path).get("media", [])}
    board = next((b for b in manifest.get("boards", []) if b["board_id"] not in done), None)
    if not board:
        print("No eligible board tasks")
        return
    prompt_path = run / board["prompt_path"].removeprefix("./")
    register = f"python scripts/register_storyboard_result.py {run} {board['board_id']} <generated-file>"
    print(json.dumps({
        "action": "call_builtin_image_tool",
        "board_id": board["board_id"],
        "prompt_path": str(prompt_path),
        "expected_output": "exactly_one_image",
        "contract": "只喂本 board 的 prompt_path，生成且仅生成 1 张图；禁止读取 manifest 或其它 SB 板提示词，禁止把多个分镜板合并到一张图。",
        "register_with": register,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
