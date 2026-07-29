#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def resolve_max_seconds(run_dir: Path, cli_max_seconds: float | None) -> float:
    """从 vertical 配置读取 max_generated_clip_seconds；命令行参数可覆盖；兜底 30。"""
    if cli_max_seconds is not None:
        return cli_max_seconds
    checkpoint_path = run_dir / "checkpoint.json"
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        vertical_id = checkpoint.get("vertical", {}).get("id")
        if vertical_id:
            vertical_path = run_dir.parent.parent / "config" / "verticals" / f"{vertical_id}.yaml"
            if vertical_path.exists():
                import re
                text = vertical_path.read_text(encoding="utf-8")
                match = re.search(r"max_generated_clip_seconds:\s*(\d+)", text)
                if match:
                    return float(match.group(1))
    return 30.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hard-rule merge candidates for AI review; never writes an approved plan.")
    parser.add_argument("run_dir")
    parser.add_argument("--max-seconds", type=float, default=None,
                        help="镜头组上限秒数；不传则从 vertical 配置读取 max_generated_clip_seconds")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    max_seconds = resolve_max_seconds(run_dir, args.max_seconds)
    outputs = run_dir / "outputs"
    shots = json.loads((outputs / "storyboard.json").read_text(encoding="utf-8"))["shots"]
    segments, current = [], []
    for shot in shots:
        total = sum(x["duration_seconds"] for x in current)
        if current and (shot["scene_id"] != current[-1]["scene_id"] or total + shot["duration_seconds"] > max_seconds):
            segments.append(current); current = []
        current.append(shot)
    if current:
        segments.append(current)
    result = []
    for i, rows in enumerate(segments, 1):
        source = [x["shot_id"] for x in rows]
        result.append({
            "candidate_id": f"CAND-{i:03d}", "source_shots": source, "scene_id": rows[0]["scene_id"],
            "duration_seconds": sum(x["duration_seconds"] for x in rows),
            "hard_constraints_passed": True,
            "requires_ai_decision": len(rows) > 1
        })
    target = outputs / "drafts/video_segment_candidates.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"candidates": result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result)} candidates for AI review (max_segment_seconds={max_seconds})")


if __name__ == "__main__":
    main()
