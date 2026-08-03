#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


TRANSIENT_TERMS = {"接电话", "哭泣", "愤怒", "微笑", "走路", "坐下", "站立", "中景", "全景", "特写", "俯视", "仰视"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Flag invalid or suspicious asset variants.")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    path = Path(args.run_dir).resolve() / "outputs/asset_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    errors, warnings = [], []
    ids, names = set(), set()
    for group in ("characters", "scenes", "props"):
        for item in data.get(group, []):
            aid, name = item.get("asset_id"), item.get("asset_name", "")
            if aid in ids or name in names:
                errors.append(f"duplicate asset identity or name: {aid} / {name}")
            ids.add(aid); names.add(name)
            if "状态" in name:
                errors.append(f"forbidden 状态 suffix/token: {name}")
            if group == "characters" and any(term in name for term in TRANSIENT_TERMS):
                warnings.append(f"possible transient character variant: {name}")
            if item.get("generation_required") and not item.get("output_prompt_path"):
                errors.append(f"missing prompt path: {name}")
    for line in warnings:
        print("WARN: " + line)
    for line in errors:
        print("FAIL: " + line)
    if errors:
        raise SystemExit(1)
    print(f"OK: {len(ids)} assets, {len(warnings)} semantic warnings")


if __name__ == "__main__":
    main()
