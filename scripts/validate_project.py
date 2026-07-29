#!/usr/bin/env python3
"""Validate a production-focused short-video local run."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any
from pipeline_runtime import STAGES

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
MAX_DURATION = 15
FRAME_ROLES = {"first_frame", "last_frame", "keyframe"}
PIPELINE = STAGES
PHASE_ALIASES = {
    "init": "initialized",
    "art_direction": "art",
    "asset_executor": "assets",
    "asset_prompts": "asset_prompt_generation",
    "storyboard_prompts": "storyboard_prompt_generation",
    "video": "video_prompts",
}
FORBIDDEN_STORYBOARD_FIELDS = {
    "characters_in_shot",
    "location",
    "character_ids",
    "prop_ids",
    "asset_ids",
    "prompt_cn",
}
VIDEO_SECTIONS = ["【自检通过项】", "【资产声明区】", "【中文视频提示词】"]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"OK: {message}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON: {path} ({exc})")
    if not isinstance(data, dict):
        fail(f"JSON root must be object: {path}")
    return data


def require_file(path: Path) -> None:
    if not path.is_file():
        fail(f"Required file missing: {path}")


def require_dir(path: Path) -> None:
    if not path.is_dir():
        fail(f"Required directory missing: {path}")


def schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_schema_subset(data: Any, schema: dict[str, Any], label: str) -> None:
    defs = schema.get("$defs", {})

    def resolve(node: dict[str, Any]) -> dict[str, Any]:
        ref = node.get("$ref")
        if not ref:
            return node
        name = ref.removeprefix("#/$defs/")
        if name not in defs:
            fail(f"{label}: missing schema def {name}")
        merged = dict(defs[name])
        merged.update({k: v for k, v in node.items() if k != "$ref"})
        return merged

    def check(value: Any, node: dict[str, Any], path: str) -> None:
        node = resolve(node)
        expected_type = node.get("type")
        if expected_type is not None:
            types = expected_type if isinstance(expected_type, list) else [expected_type]
            if not any(schema_type_matches(value, t) for t in types):
                fail(f"{label}: {path} expected {types}, got {type(value).__name__}")
        if "enum" in node and value not in node["enum"]:
            fail(f"{label}: {path} value {value!r} not allowed")
        if isinstance(value, str) and "pattern" in node and not re.search(node["pattern"], value):
            fail(f"{label}: {path} value {value!r} does not match {node['pattern']}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in node and value < node["minimum"]:
                fail(f"{label}: {path} below minimum {node['minimum']}")
            if "exclusiveMinimum" in node and value <= node["exclusiveMinimum"]:
                fail(f"{label}: {path} must be greater than {node['exclusiveMinimum']}")
            if "maximum" in node and value > node["maximum"]:
                fail(f"{label}: {path} above maximum {node['maximum']}")
        if isinstance(value, dict):
            for key in node.get("required", []):
                if key not in value:
                    fail(f"{label}: {path}.{key} is required")
            for key, child_schema in node.get("properties", {}).items():
                if key in value:
                    check(value[key], child_schema, f"{path}.{key}")
        if isinstance(value, list) and "items" in node:
            for i, item in enumerate(value):
                check(item, node["items"], f"{path}[{i}]")

    check(data, schema, "$")
    ok(f"schema valid: {label}")


def validate_schema_file(data_path: Path, schema_name: str) -> dict[str, Any]:
    require_file(data_path)
    schema_path = SCHEMA_DIR / schema_name
    require_file(schema_path)
    data = read_json(data_path)
    validate_schema_subset(data, read_json(schema_path), data_path.name)
    return data


def outputs(run_dir: Path) -> Path:
    return run_dir / "outputs"


def validate_initialized(run_dir: Path) -> None:
    checkpoint = read_json(run_dir / "checkpoint.json")
    if checkpoint.get("phase_order") != PIPELINE:
        fail("checkpoint.phase_order does not match pipeline")
    for rel in ["inputs", "outputs/assets/characters", "outputs/assets/scenes", "outputs/assets/props", "outputs/storyboards"]:
        require_dir(run_dir / rel)
    require_file(run_dir / "inputs/idea_brief.md")
    ok("initialized")


def validate_story(run_dir: Path) -> None:
    require_file(outputs(run_dir) / "story.md")
    if (outputs(run_dir) / "story.json").exists():
        fail("story.json is deprecated")
    ok("story")


def validate_art(run_dir: Path) -> None:
    path = outputs(run_dir) / "style_bible.md"
    require_file(path)
    text = path.read_text(encoding="utf-8")
    for heading in ["画面风格", "整体色调", "光线风格", "AI 视觉执行要求"]:
        if heading not in text:
            fail(f"style_bible.md missing {heading}")
    if "## 构图倾向" in text or "## 禁止出现的视觉元素" in text:
        fail("style_bible.md contains forbidden hard section")
    ok("style bible")


def validate_storyboard(run_dir: Path) -> dict[str, Any]:
    storyboard = validate_schema_file(outputs(run_dir) / "storyboard.json", "storyboard.schema.json")
    shots = storyboard.get("shots", [])
    if not shots:
        fail("storyboard.json has no shots")
    for i, shot in enumerate(shots, start=1):
        expected = f"S{i:03d}"
        if shot.get("shot_id") != expected:
            fail(f"expected {expected}, got {shot.get('shot_id')}")
        if not re.fullmatch(r"SC[0-9]{3}", str(shot.get("scene_id"))):
            fail(f"{expected} scene_id must match SC###")
        duration = shot.get("duration_seconds")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0 or duration > MAX_DURATION:
            fail(f"{expected} duration_seconds must be >0 and <= {MAX_DURATION}")
        forbidden = sorted(FORBIDDEN_STORYBOARD_FIELDS.intersection(shot.keys()))
        if forbidden:
            fail(f"{expected} contains later-stage fields: {', '.join(forbidden)}")
    ok(f"storyboard shots: {len(shots)}")
    return storyboard


def validate_assets(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    storyboard = validate_storyboard(run_dir)
    manifest = validate_schema_file(outputs(run_dir) / "asset_manifest.json", "asset_manifest.schema.json")
    shot_map = validate_schema_file(outputs(run_dir) / "shot_asset_map.json", "shot_asset_map.schema.json")
    names = {item["asset_name"] for group in ("characters", "scenes", "props") for item in manifest.get(group, [])}
    if any(re.match(r"^(CHAR|ENV|PROP|AUDIO)_[0-9]{3}$", name) for name in names):
        fail("asset names must not use abstract IDs")
    for group in ("characters", "scenes", "props"):
        for item in manifest.get(group, []) or []:
            if "prompt_outputs" in item:
                fail("use output_prompt_path, not prompt_outputs")
            if item.get("generation_required") is True and not item.get("output_prompt_path"):
                fail(f"{item.get('asset_name')} missing output_prompt_path")
    valid_shots = {shot["shot_id"] for shot in storyboard["shots"]}
    mapped_shots = [row.get("shot_id") for row in shot_map.get("shot_assets", [])]
    if len(mapped_shots) != len(set(mapped_shots)):
        fail("shot_asset_map contains duplicate shot_id entries")
    if valid_shots != set(mapped_shots):
        fail("shot_asset_map must cover every storyboard shot exactly once")
    for row in shot_map.get("shot_assets", []) or []:
        for group in ("characters", "scenes", "props"):
            missing = sorted(set(row.get(group, []) or []) - names)
            if missing:
                fail(f"{row.get('shot_id')} references unknown {group}: {', '.join(missing)}")
    ok("assets")
    return manifest, shot_map


def validate_asset_prompt_generation(run_dir: Path) -> None:
    manifest, _ = validate_assets(run_dir)
    for group in ("characters", "scenes", "props"):
        for item in manifest.get(group, []) or []:
            prompt_path = item.get("output_prompt_path")
            if item.get("generation_required") is True and prompt_path:
                require_file(run_dir / prompt_path.removeprefix("./"))
    ok("asset prompts")


def validate_image_queue(run_dir: Path) -> None:
    path = outputs(run_dir) / "image_generation_queue.json"
    if not path.is_file():
        return
    queue = validate_schema_file(path, "image_generation_queue.schema.json")
    task_ids = [x["task_id"] for x in queue["tasks"]]
    asset_ids = [x["asset_id"] for x in queue["tasks"]]
    if len(task_ids) != len(set(task_ids)) or len(asset_ids) != len(set(asset_ids)):
        fail("image queue contains duplicate task_id or asset_id")
    ok("image queue")


def shot_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^##\s+(S[0-9]{3})\b", text))
    return {
        match.group(1): text[match.start() : matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        for i, match in enumerate(matches)
    }


def field(section: str, name: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(name)}\s*:\s*([^\n]+)", section)
    return match.group(1).strip() if match else None


def validate_storyboard_prompt_generation(run_dir: Path) -> None:
    storyboard = validate_storyboard(run_dir)
    require_file(outputs(run_dir) / "storyboard_prompts.md")
    sections = shot_sections((outputs(run_dir) / "storyboard_prompts.md").read_text(encoding="utf-8"))
    shots = storyboard["shots"]
    by_id = {shot["shot_id"]: shot for shot in shots}
    for i, shot in enumerate(shots):
        shot_id = shot["shot_id"]
        section = sections.get(shot_id)
        if not section:
            fail(f"storyboard_prompts.md missing {shot_id}")
        role = field(section, "frame_role") or field(section, "recommended_frame_role")
        if role not in FRAME_ROLES:
            fail(f"{shot_id} missing valid frame_role")
        uses_previous = field(section, "uses_previous_storyboard_reference")
        if uses_previous not in {"true", "false"}:
            fail(f"{shot_id} missing uses_previous_storyboard_reference")
        if uses_previous == "true":
            if i == 0:
                fail(f"{shot_id} cannot reference previous storyboard")
            previous_id = shots[i - 1]["shot_id"]
            if field(section, "source_shot_id") != previous_id:
                fail(f"{shot_id} previous reference must be {previous_id}")
            if by_id[previous_id]["scene_id"] != shot["scene_id"]:
                fail(f"{shot_id} must not reference previous storyboard across scene_id")
            if "placement_anchor" not in section and "站位" not in section:
                fail(f"{shot_id} previous reference must be placement-only")
    ok("storyboard prompts")


def validate_storyboard_sequence_review(run_dir: Path) -> None:
    review = validate_schema_file(outputs(run_dir) / "reviews/storyboard_sequence_review.json", "storyboard_sequence_review.schema.json")
    if review.get("status") != "pass" or any(x.get("severity") == "P0" for x in review.get("issues", [])):
        fail("storyboard sequence review has unresolved blockers")
    ok("storyboard sequence review")


def validate_video_segment_plan(run_dir: Path) -> None:
    storyboard = validate_storyboard(run_dir)
    plan = validate_schema_file(outputs(run_dir) / "video_segment_plan.json", "video_segment_plan.schema.json")
    shot_index = {x["shot_id"]: i for i, x in enumerate(storyboard["shots"])}
    covered = []
    for i, segment in enumerate(plan["segments"], 1):
        if segment["video_id"] != f"V{i:03d}":
            fail("video segment ids must be sequential")
        source = segment["source_shots"]
        indexes = [shot_index[x] for x in source]
        if indexes != list(range(min(indexes), max(indexes) + 1)):
            fail(f"{segment['video_id']} source shots must be contiguous")
        rows = [storyboard["shots"][x] for x in indexes]
        if {x["scene_id"] for x in rows} != {segment["scene_id"]}:
            fail(f"{segment['video_id']} crosses scene boundary")
        if not math.isclose(sum(x["duration_seconds"] for x in rows), segment["duration_seconds"]):
            fail(f"{segment['video_id']} duration mismatch")
        roles = [x["role"] for x in segment["frame_plan"]]
        frame_shots = [x["shot_id"] for x in segment["frame_plan"]]
        if frame_shots != source:
            fail(f"{segment['video_id']} frame plan must cover source shots in order")
        if len(source) == 1 and roles != ["first_frame"]:
            fail(f"{segment['video_id']} single shot must be first_frame")
        if len(source) > 1 and (roles[0] != "first_frame" or roles[-1] != "last_frame" or any(x != "keyframe" for x in roles[1:-1])):
            fail(f"{segment['video_id']} has invalid endpoint or keyframe roles")
        covered.extend(source)
    if covered != [x["shot_id"] for x in storyboard["shots"]]:
        fail("video segment plan must cover every shot exactly once and in order")
    ok("video segment plan")


def validate_storyboard_visual_review(run_dir: Path) -> None:
    review = validate_schema_file(outputs(run_dir) / "reviews/storyboard_visual_review.json", "storyboard_visual_review.schema.json")
    if review.get("status") != "pass" or any(x.get("severity") == "P0" for x in review.get("issues", [])):
        fail("storyboard visual review has unresolved blockers")
    ok("storyboard visual review")


def validate_video_prompt_plan(run_dir: Path, storyboard: dict[str, Any]) -> None:
    plan = validate_schema_file(outputs(run_dir) / "video_prompts.json", "video_prompt.schema.json")
    shots = storyboard["shots"]
    shot_by_id = {shot["shot_id"]: shot for shot in shots}
    shot_index = {shot["shot_id"]: i for i, shot in enumerate(shots)}
    videos = plan.get("videos", [])
    if not videos:
        fail("video_prompts.json has no videos")
    covered: list[str] = []
    for i, video in enumerate(videos, start=1):
        video_id = f"V{i:03d}"
        if video.get("video_id") != video_id:
            fail(f"expected {video_id}, got {video.get('video_id')}")
        if video.get("task_type") != "pipeline_shot_generation":
            fail(f"{video_id} must be pipeline_shot_generation")
        source_shots = video.get("source_shots", [])
        if not isinstance(source_shots, list) or not source_shots:
            fail(f"{video_id} source_shots must be a non-empty list")
        if len(source_shots) != len(set(source_shots)):
            fail(f"{video_id} source_shots contains duplicates")
        unknown = [sid for sid in source_shots if sid not in shot_index]
        if unknown:
            fail(f"{video_id} source_shots references unknown shots: {', '.join(unknown)}")
        indexes = [shot_index[sid] for sid in source_shots]
        if indexes != list(range(min(indexes), max(indexes) + 1)):
            fail(f"{video_id} source_shots must be contiguous and ordered")
        scenes = {shot_by_id[sid]["scene_id"] for sid in source_shots}
        if scenes != {video.get("scene_id")}:
            fail(f"{video_id} scene_id must match all source_shots")
        duration_sum = sum(shot_by_id[sid]["duration_seconds"] for sid in source_shots)
        if duration_sum > MAX_DURATION:
            fail(f"{video_id} merged duration exceeds {MAX_DURATION}s")
        declared_duration = video.get("duration_seconds")
        if not isinstance(declared_duration, (int, float)) or isinstance(declared_duration, bool):
            fail(f"{video_id} duration_seconds must be numeric")
        if not math.isclose(float(declared_duration), float(duration_sum), rel_tol=0, abs_tol=1e-6):
            fail(f"{video_id} duration_seconds must equal source_shots sum ({duration_sum})")
        strategy = video["merge_decision"]["strategy"]
        if len(source_shots) > 1 and not strategy.startswith("merged_"):
            fail(f"{video_id} merged shots require merged_* strategy")
        if len(source_shots) == 1 and strategy.startswith("merged_"):
            fail(f"{video_id} single shot must not use merged_* strategy")
        frame_shots = {frame["shot_id"] for frame in video.get("frame_references", [])}
        if frame_shots != set(source_shots):
            fail(f"{video_id} frame_references must match source_shots")
        covered.extend(source_shots)
    if sorted(covered) != sorted(shot_by_id):
        fail("video_prompts.json must cover every shot exactly once")


def validate_video_prompts(run_dir: Path) -> None:
    storyboard = validate_storyboard(run_dir)
    require_file(outputs(run_dir) / "video_prompts.md")
    text = (outputs(run_dir) / "video_prompts.md").read_text(encoding="utf-8")
    for section in VIDEO_SECTIONS:
        if section not in text:
            fail(f"video_prompts.md missing {section}")
    if "English Prompt" in text or "中英对照" in text or "@PROP" in text:
        fail("video_prompts.md contains forbidden block or @PROP")
    if "画面保持无字幕" not in text or "Logo" not in text or "水印" not in text:
        fail("video_prompts.md missing no-subtitle/no-logo/no-watermark constraint")
    validate_video_prompt_plan(run_dir, storyboard)
    ok("video prompts")


def validate_all(run_dir: Path) -> None:
    validate_initialized(run_dir)
    validate_story(run_dir)
    validate_art(run_dir)
    validate_storyboard_sequence_review(run_dir)
    validate_assets(run_dir)
    validate_asset_prompt_generation(run_dir)
    validate_image_queue(run_dir)
    validate_video_segment_plan(run_dir)
    validate_storyboard_prompt_generation(run_dir)
    validate_storyboard_visual_review(run_dir)
    validate_video_prompts(run_dir)


def validate_structure_level(run_dir: Path) -> None:
    validate_initialized(run_dir)
    validate_story(run_dir)
    validate_art(run_dir)
    validate_storyboard(run_dir)
    validate_assets(run_dir)
    if (outputs(run_dir) / "video_segment_plan.json").is_file():
        validate_video_segment_plan(run_dir)
    ok("structure level")


def validate_draft_level(run_dir: Path) -> None:
    validate_structure_level(run_dir)
    validate_storyboard_sequence_review(run_dir)
    validate_asset_prompt_generation(run_dir)
    validate_image_queue(run_dir)
    validate_video_segment_plan(run_dir)
    validate_storyboard_prompt_generation(run_dir)
    if (outputs(run_dir) / "video_prompts.json").is_file():
        validate_video_prompts(run_dir)
    ok("draft level")


def validate_production_level(run_dir: Path) -> None:
    validate_draft_level(run_dir)
    manifest = read_json(outputs(run_dir) / "asset_manifest.json")
    for group in ("characters", "scenes", "props"):
        for item in manifest.get(group, []):
            if not item.get("generation_required"):
                continue
            if item.get("approval_status") != "approved":
                fail(f"production: asset not approved: {item.get('asset_name')}")
            canonical = item.get("canonical_path")
            if not canonical:
                fail(f"production: asset missing canonical_path: {item.get('asset_name')}")
            require_file(run_dir / canonical.removeprefix("./"))
            review_path = item.get("review_report_path")
            if not review_path:
                fail(f"production: asset missing review report: {item.get('asset_name')}")
            review = validate_schema_file(run_dir / review_path.removeprefix("./"), "generated_asset_review.schema.json")
            if review.get("status") != "pass" or review.get("asset_version") != item.get("version"):
                fail(f"production: asset review invalid/stale: {item.get('asset_name')}")
    storyboard = read_json(outputs(run_dir) / "storyboard.json")
    for shot in storyboard["shots"]:
        require_file(outputs(run_dir) / "approved/storyboard_prompts" / f"{shot['shot_id']}.md")
        require_file(outputs(run_dir) / "approved/storyboards" / f"{shot['shot_id']}.png")
    validate_storyboard_visual_review(run_dir)
    plan = read_json(outputs(run_dir) / "video_segment_plan.json")
    for segment in plan["segments"]:
        require_file(outputs(run_dir) / "approved/video_generation" / segment["video_id"] / "prompt.txt")
        require_file(outputs(run_dir) / "approved/video_generation" / segment["video_id"] / "manifest.json")
    final_path = outputs(run_dir) / "final_package_manifest.json"
    require_file(final_path)
    final = validate_schema_file(final_path, "final_package_manifest.schema.json")
    if final.get("status") != "completed":
        fail(f"production: final package status is {final.get('status')}")
    checkpoint = read_json(run_dir / "checkpoint.json")
    if checkpoint.get("vertical", {}).get("id") == "advertising":
        story_path = outputs(run_dir) / "story.md"
        story_text = story_path.read_text(encoding="utf-8")
        if "## 商业信息" not in story_text:
            fail("production: advertising story.md missing '## 商业信息' section")
    ok("production level")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a short-video local run.")
    parser.add_argument("run_dir")
    parser.add_argument("--level", choices=["structure", "draft", "production"])
    parser.add_argument(
        "--phase",
        default="all",
        choices=[
            "initialized",
            "init",
            "story",
            "art",
            "art_direction",
            "storyboard",
            "storyboard_sequence_review",
            "assets",
            "asset_executor",
            "asset_prompt_generation",
            "asset_prompts",
            "storyboard_prompt_generation",
            "storyboard_prompts",
            "video_segment_plan",
            "storyboard_visual_review",
            "video_prompts",
            "video",
            "all",
        ],
    )
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    if args.level:
        {"structure": validate_structure_level, "draft": validate_draft_level, "production": validate_production_level}[args.level](run_dir)
        print("VALIDATION PASSED")
        return
    phase = PHASE_ALIASES.get(args.phase, args.phase)
    validators = {
        "initialized": validate_initialized,
        "story": validate_story,
        "art": validate_art,
        "storyboard": validate_storyboard,
        "storyboard_sequence_review": validate_storyboard_sequence_review,
        "assets": validate_assets,
        "asset_prompt_generation": validate_asset_prompt_generation,
        "storyboard_prompt_generation": validate_storyboard_prompt_generation,
        "video_segment_plan": validate_video_segment_plan,
        "storyboard_visual_review": validate_storyboard_visual_review,
        "video_prompts": validate_video_prompts,
        "all": validate_all,
    }
    validators[phase](run_dir)
    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()
