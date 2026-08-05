#!/usr/bin/env python3
"""Validate a production-focused short-video local run."""

from __future__ import annotations

import argparse
import json
import math
import re
import hashlib
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator
from pipeline_runtime import SPEC, STAGES
from path_safety import resolve_in_run
from artifact_runtime import (
    digest_path, verify_artifact_approval, verify_storyboard_text_approval,
    verify_stage_approvals, verify_stage_integrity,
)
from pipeline_runtime import APPROVAL_REQUIRED

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
MAX_SHOT_DURATION = 10
MIN_SEGMENT_DURATION = SPEC["production_constraints"]["video_segment_duration_seconds"]["minimum"]
MAX_SEGMENT_DURATION = SPEC["production_constraints"]["video_segment_duration_seconds"]["maximum"]
DEFAULT_ASPECT_RATIO = SPEC["production_defaults"]["video_aspect_ratio"]
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
VIDEO_SECTIONS = ["素材：", "提示词：", "约束："]
# 资产类型 → 强制参考图画幅约定（人物 21:9，场景 16:9，物品 16:9）
# 键使用 asset_manifest.json 的 schema 组名（复数）。
_REFERENCE_LAYOUT_BY_TYPE = {
    "characters": "character_turnaround_21x9_v1",
    "scenes": "scene_keyplate_quad_v1",
    "props": "prop_single_reference_v1",
}


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


def project_aspect_ratio(run_dir: Path) -> str:
    checkpoint = read_json(run_dir / "checkpoint.json")
    value = checkpoint.get("ad_production", {}).get("aspect_ratio") or DEFAULT_ASPECT_RATIO
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", value):
        fail(f"invalid video aspect ratio: {value!r}")
    return value


def require_file(path: Path) -> None:
    if not path.is_file():
        fail(f"Required file missing: {path}")


def require_dir(path: Path) -> None:
    if not path.is_dir():
        fail(f"Required directory missing: {path}")


def validate_schema_subset(data: Any, schema: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        path = ".".join(str(x) for x in error.absolute_path) or "$"
        fail(f"{label}: {path}: {error.message}")
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
    if checkpoint.get("schema_version") != SPEC["schema_version"]:
        fail(f"checkpoint schema must be {SPEC['schema_version']}; migrate the run")
    if checkpoint.get("phase_order") != PIPELINE:
        fail("checkpoint.phase_order does not match pipeline")
    for rel in ["inputs", "outputs/assets/characters", "outputs/assets/scenes", "outputs/assets/props", "outputs/storyboard_boards", "outputs/video_prompts"]:
        require_dir(run_dir / rel)
    require_file(run_dir / "inputs/idea_brief.md")
    ok("initialized")


def validate_story(run_dir: Path) -> None:
    require_file(outputs(run_dir) / "brief.md")
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
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0 or duration > MAX_SHOT_DURATION:
            fail(f"{expected} duration_seconds must be >0 and <= {MAX_SHOT_DURATION}")
        forbidden = sorted(FORBIDDEN_STORYBOARD_FIELDS.intersection(shot.keys()))
        if forbidden:
            fail(f"{expected} contains later-stage fields: {', '.join(forbidden)}")
    checkpoint_path = run_dir / "checkpoint.json"
    if checkpoint_path.is_file():
        target_duration = read_json(checkpoint_path).get("ad_production", {}).get("duration_seconds")
        if isinstance(target_duration, (int, float)) and not isinstance(target_duration, bool):
            actual_duration = sum(shot["duration_seconds"] for shot in shots)
            if not math.isclose(actual_duration, target_duration, rel_tol=0, abs_tol=0.5):
                fail(f"storyboard total duration {actual_duration}s does not match target {target_duration}s within 0.5s")
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
            if item.get("output_prompt_path"):
                try:
                    resolve_in_run(run_dir, item["output_prompt_path"])
                except ValueError as exc:
                    fail(str(exc))
            if group == "props" and item.get("business_role") == "advertised_product" and item.get("generation_required") is not True:
                fail(f"advertised product must generate an independent reference: {item.get('asset_name')}")
            # 画幅 / reference_layout 硬校验（人物 21:9，场景 16:9，物品 16:9）
            expected_layout = _REFERENCE_LAYOUT_BY_TYPE.get(group)
            layout = item.get("reference_layout")
            if item.get("generation_required") is True and expected_layout and layout != expected_layout:
                fail(
                    f"{group} asset {item.get('asset_name')} must use reference_layout "
                    f"{expected_layout}, got {layout!r}"
                )
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
    prompt_manifest = validate_schema_file(outputs(run_dir) / "asset_prompt_manifest.json", "asset_prompt_manifest.schema.json")
    prompt_rows = {row["asset_id"]: row for row in prompt_manifest["prompts"]}
    expected = set()
    for group in ("characters", "scenes", "props"):
        for item in manifest.get(group, []) or []:
            prompt_path = item.get("output_prompt_path")
            if item.get("generation_required") is True and prompt_path:
                expected.add(item["asset_id"])
                row = prompt_rows.get(item["asset_id"])
                if not row or row["prompt_path"] != prompt_path:
                    fail(f"asset prompt manifest mismatch: {item['asset_id']}")
                prompt = resolve_in_run(run_dir, row["prompt_path"], must_exist=True)
                if digest_path(prompt) != row["sha256"]:
                    fail(f"asset prompt hash mismatch: {item['asset_id']}")
    if expected != set(prompt_rows):
        fail("asset prompt manifest must cover every generated asset exactly once")
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


def validate_registries(run_dir: Path, required: bool = False) -> None:
    artifact_path = outputs(run_dir) / "artifact_registry.json"
    approval_path = outputs(run_dir) / "approval_registry.json"
    if not artifact_path.is_file() or not approval_path.is_file():
        if required:
            fail("production: artifact_registry.json and approval_registry.json are required")
        return
    artifact_registry = validate_schema_file(artifact_path, "artifact_registry.schema.json")
    approval_registry = validate_schema_file(approval_path, "approval_registry.schema.json")
    artifact_id_list = [row["artifact_revision_id"] for row in artifact_registry["artifacts"]]
    artifact_ids = set(artifact_id_list)
    if len(artifact_ids) != len(artifact_id_list):
        fail("artifact registry contains duplicate revision ids")
    approval_ids = [row["approval_id"] for row in approval_registry["approvals"]]
    if len(set(approval_ids)) != len(approval_ids):
        fail("approval registry contains duplicate approval ids")
    for approval in approval_registry["approvals"]:
        if approval["artifact_revision_id"] not in artifact_ids:
            fail(f"approval references unknown artifact: {approval['artifact_revision_id']}")
    latest_revision = {}
    for row in artifact_registry["artifacts"]:
        latest_revision[row["artifact_name"]] = max(latest_revision.get(row["artifact_name"], 0), row["revision"])
    for row in artifact_registry["artifacts"]:
        missing_dependencies = sorted(set(row["dependencies"]) - artifact_ids)
        if missing_dependencies:
            fail(f"artifact {row['artifact_revision_id']} has unknown dependencies: {', '.join(missing_dependencies)}")
        try:
            snapshot = resolve_in_run(run_dir, row["snapshot_path"], must_exist=True)
        except ValueError as exc:
            fail(str(exc))
        if digest_path(snapshot) != row["sha256"]:
            fail(f"artifact registry integrity mismatch: {row['artifact_revision_id']}")
        if row["revision"] == latest_revision[row["artifact_name"]]:
            try:
                canonical = resolve_in_run(run_dir, row["canonical_path"], must_exist=True)
            except ValueError as exc:
                fail(str(exc))
            if digest_path(canonical) != row["sha256"]:
                fail(f"artifact registry latest canonical mismatch: {row['artifact_revision_id']}")
    ok("artifact and approval registries")


def validate_storyboard_prompt_generation(run_dir: Path) -> None:
    storyboard = validate_storyboard(run_dir)
    validate_video_segment_plan(run_dir)
    plan = read_json(outputs(run_dir) / "video_segment_plan.json")
    manifest = validate_schema_file(outputs(run_dir) / "storyboard_board_manifest.json", "storyboard_board_manifest.schema.json")
    board_ids, covered_shots = [], []
    expected_by_video = {row["video_id"]: row["source_shots"] for row in plan["segments"]}
    covered_by_video = {video_id: [] for video_id in expected_by_video}
    seven_elements = ["景别", "机位", "主体", "动作定格", "构图", "环境", "光线"]
    for index, board in enumerate(manifest["boards"], start=1):
        expected_board_id = f"SB{index:03d}"
        if board["board_id"] != expected_board_id:
            fail(f"expected {expected_board_id}, got {board['board_id']}")
        if board["video_id"] not in expected_by_video:
            fail(f"{board['board_id']} references unknown video {board['video_id']}")
        try:
            board_file = resolve_in_run(run_dir, board["prompt_path"], must_exist=True)
            resolve_in_run(run_dir, board["packet_path"], must_exist=True)
        except ValueError as exc:
            fail(str(exc))
        text = board_file.read_text(encoding="utf-8")
        if not board.get("prompt_hash") or digest_path(board_file) != board["prompt_hash"]:
            fail(f"{board['board_id']} prompt hash mismatch")
        if not any(elem in text for elem in seven_elements):
            fail(f"{board_file.name} missing seven-element画面描述")
        mentioned = {match.group(1) for match in re.finditer(r"\b(S[0-9]{3})\b", text)}
        if not set(board["shot_ids"]).issubset(mentioned):
            fail(f"{board['board_id']} prompt does not mention all declared shots")
        board_shots = [shot for shot in storyboard["shots"] if shot["shot_id"] in board["shot_ids"]]
        expected_required_text = [
            {"shot_id": shot["shot_id"], **item}
            for shot in board_shots
            for item in shot["advertising_text"]
        ]
        if board["required_text"] != expected_required_text:
            fail(f"{board['board_id']} required_text does not match storyboard")
        expected_duration = sum(shot["duration_seconds"] for shot in board_shots)
        if not math.isclose(board["duration_seconds"], expected_duration):
            fail(f"{board['board_id']} duration does not match storyboard")
        for item in expected_required_text:
            if item["content"] not in text:
                fail(f"{board['board_id']} prompt omits declared advertising text: {item['content']}")
        if expected_required_text and ("无文字" in text or "不出现任何文字" in text):
            fail(f"{board['board_id']} prompt forbids its declared advertising text")
        board_ids.append(board["board_id"])
        covered_shots.extend(board["shot_ids"])
        covered_by_video[board["video_id"]].extend(board["shot_ids"])
    expected_shots = [shot["shot_id"] for shot in storyboard["shots"]]
    if covered_shots != expected_shots or len(covered_shots) != len(set(covered_shots)):
        fail("storyboard board manifest must cover every shot exactly once and in order")
    for video_id, expected in expected_by_video.items():
        if covered_by_video[video_id] != expected:
            fail(f"{video_id} board mapping does not cover source shots in order")
    ok("storyboard boards")


def validate_video_segment_plan(run_dir: Path) -> None:
    storyboard = validate_storyboard(run_dir)
    plan = validate_schema_file(outputs(run_dir) / "video_segment_plan.json", "video_segment_plan.schema.json")
    shot_index = {x["shot_id"]: i for i, x in enumerate(storyboard["shots"])}
    covered = []
    for i, segment in enumerate(plan["segments"], 1):
        if segment["video_id"] != f"V{i:03d}":
            fail("video segment ids must be sequential")
        source = segment["source_shots"]
        if not MIN_SEGMENT_DURATION <= segment["duration_seconds"] <= MAX_SEGMENT_DURATION:
            fail(
                f"{segment['video_id']} duration must be between "
                f"{MIN_SEGMENT_DURATION} and {MAX_SEGMENT_DURATION} seconds"
            )
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


def validate_video_prompts(run_dir: Path) -> None:
    storyboard = validate_storyboard(run_dir)
    plan = read_json(outputs(run_dir) / "video_segment_plan.json")
    board_manifest = read_json(outputs(run_dir) / "storyboard_board_manifest.json")
    manifest = validate_schema_file(outputs(run_dir) / "video_prompt_manifest.json", "video_prompt_manifest.schema.json")
    asset_manifest, shot_asset_map = validate_assets(run_dir)
    shot_assets = {row["shot_id"]: row for row in shot_asset_map["shot_assets"]}
    props = {row["asset_name"]: row for row in asset_manifest.get("props", [])}
    forbidden_scene_refs = [row["asset_name"] for row in asset_manifest.get("scenes", [])]
    forbidden_prop_refs = [
        row["asset_name"] for row in asset_manifest.get("props", [])
        if row.get("business_role") != "advertised_product"
    ]
    aspect_ratio = project_aspect_ratio(run_dir)
    shots_by_id = {row["shot_id"]: row for row in storyboard["shots"]}
    expected = {row["video_id"]: row for row in plan["segments"]}
    board_by_video = {}
    for board in board_manifest["boards"]:
        board_by_video.setdefault(board["video_id"], []).append(board["board_id"])
    if [row["video_id"] for row in manifest["videos"]] != list(expected):
        fail("video prompt manifest ids must match segment plan in order")
    for video in manifest["videos"]:
        segment = expected[video["video_id"]]
        if video["source_shots"] != segment["source_shots"] or not math.isclose(video["duration_seconds"], segment["duration_seconds"]):
            fail(f"{video['video_id']} prompt manifest does not match segment plan")
        if video["aspect_ratio"] != aspect_ratio:
            fail(f"{video['video_id']} aspect ratio must be {aspect_ratio}")
        if video["source_boards"] != board_by_video.get(video["video_id"], []):
            fail(f"{video['video_id']} source_boards do not match board manifest")
        try:
            prompt_file = resolve_in_run(run_dir, video["prompt_path"], must_exist=True)
        except ValueError as exc:
            fail(str(exc))
        if digest_path(prompt_file) != video["prompt_hash"]:
            fail(f"{video['video_id']} prompt hash mismatch")
        text = prompt_file.read_text(encoding="utf-8")
        for section in VIDEO_SECTIONS:
            if section not in text:
                fail(f"{prompt_file.name} missing {section}")
        if "English Prompt" in text or "中英对照" in text or "@PROP" in text:
            fail(f"{prompt_file.name} contains forbidden block or @PROP")
        if aspect_ratio not in text:
            fail(f"{prompt_file.name} does not declare aspect ratio {aspect_ratio}")
        expected_characters = sorted({
            name for shot_id in segment["source_shots"] for name in shot_assets[shot_id]["characters"]
        })
        expected_products = sorted({
            name for shot_id in segment["source_shots"] for name in shot_assets[shot_id]["props"]
            if props[name].get("business_role") == "advertised_product"
        })
        if video["character_assets"] != expected_characters:
            fail(f"{video['video_id']} character assets do not match source shots")
        if video["product_assets"] != expected_products:
            fail(f"{video['video_id']} product assets do not match source shots")
        forbidden_refs = [name for name in forbidden_scene_refs + forbidden_prop_refs if f"@{name}" in text]
        if forbidden_refs:
            fail(f"{prompt_file.name} references forbidden scene/non-product assets: {', '.join(forbidden_refs)}")
        required_text = [
            item["content"]
            for shot_id in segment["source_shots"]
            for item in shots_by_id[shot_id]["advertising_text"]
        ]
        if required_text:
            if "保持分镜板中已经出现的广告文字" not in text or "禁止新增文字" not in text or "水印" not in text:
                fail(f"{prompt_file.name} missing locked advertising-text constraints")
            if "无文字" in text or "不出现任何文字" in text:
                fail(f"{prompt_file.name} conflicts with declared advertising text")
        elif "无字幕" not in text or "Logo" not in text or "水印" not in text:
            fail(f"{prompt_file.name} missing no-subtitle/no-logo/no-watermark constraint")
    ok("video prompts")


def validate_all(run_dir: Path) -> None:
    fail("--phase all is ambiguous and deprecated; use --level structure|draft|production|delivery")


def validate_structure_level(run_dir: Path) -> None:
    validate_initialized(run_dir)
    validate_story(run_dir)
    validate_art(run_dir)
    validate_storyboard(run_dir)
    validate_assets(run_dir)
    validate_video_segment_plan(run_dir)
    ok("structure level")


def validate_draft_level(run_dir: Path) -> None:
    validate_structure_level(run_dir)
    validate_asset_prompt_generation(run_dir)
    validate_image_queue(run_dir)
    validate_video_segment_plan(run_dir)
    validate_storyboard_prompt_generation(run_dir)
    if (outputs(run_dir) / "video_prompt_manifest.json").is_file():
        validate_video_prompts(run_dir)
    if (outputs(run_dir) / "asset_media_manifest.json").is_file():
        validate_schema_file(outputs(run_dir) / "asset_media_manifest.json", "asset_media_manifest.schema.json")
    if (outputs(run_dir) / "storyboard_media_manifest.json").is_file():
        validate_schema_file(outputs(run_dir) / "storyboard_media_manifest.json", "storyboard_media_manifest.schema.json")
    validate_registries(run_dir, required=False)
    ok("draft level")


def validate_production_level(run_dir: Path) -> None:
    validate_draft_level(run_dir)
    checkpoint = read_json(run_dir / "checkpoint.json")
    validate_registries(run_dir, required=True)
    for stage in APPROVAL_REQUIRED:
        row = checkpoint.get("stages", {}).get(stage, {})
        if row.get("status") != "approved" or not row.get("artifact_revision_ids"):
            fail(f"production: approved artifact revisions required for {stage}")
        errors = verify_stage_integrity(run_dir, checkpoint, stage) + verify_stage_approvals(run_dir, checkpoint, stage)
        if errors:
            fail(f"production: {stage}: {'; '.join(errors)}")
    draft_only_skips = [name for name, row in checkpoint.get("stages", {}).items() if row.get("status") == "skipped" and row.get("skip_effect") == "draft_only"]
    if draft_only_skips:
        fail("production: draft-only stages were skipped: " + ", ".join(draft_only_skips))
    manifest = read_json(outputs(run_dir) / "asset_manifest.json")
    asset_media_manifest = validate_schema_file(outputs(run_dir) / "asset_media_manifest.json", "asset_media_manifest.schema.json")
    asset_media = {}
    for media in asset_media_manifest["media"]:
        if media["asset_id"] not in asset_media or media["revision"] > asset_media[media["asset_id"]]["revision"]:
            asset_media[media["asset_id"]] = media
    for group in ("characters", "scenes", "props"):
        for item in manifest.get(group, []):
            if not item.get("generation_required"):
                continue
            media = asset_media.get(item["asset_id"])
            if not media:
                fail(f"production: asset media missing: {item.get('asset_name')}")
            try:
                media_path = resolve_in_run(run_dir, media["media_path"], must_exist=True)
            except ValueError as exc:
                fail(str(exc))
            if digest_path(media_path) != media["sha256"]:
                fail(f"production: asset media hash mismatch: {item.get('asset_name')}")
            approval_errors = verify_artifact_approval(run_dir, media["media_revision_id"])
            if approval_errors:
                fail(f"production: asset {item.get('asset_name')}: {'; '.join(approval_errors)}")
    board_manifest = read_json(outputs(run_dir) / "storyboard_board_manifest.json")
    storyboard_media_manifest = validate_schema_file(outputs(run_dir) / "storyboard_media_manifest.json", "storyboard_media_manifest.schema.json")
    board_media = {}
    for media in storyboard_media_manifest["media"]:
        if media["board_id"] not in board_media or media["revision"] > board_media[media["board_id"]]["revision"]:
            board_media[media["board_id"]] = media
    for board in board_manifest["boards"]:
        media = board_media.get(board["board_id"])
        if not media:
            fail(f"production: storyboard media missing: {board['board_id']}")
        try:
            media_path = resolve_in_run(run_dir, media["media_path"], must_exist=True)
        except ValueError as exc:
            fail(str(exc))
        if digest_path(media_path) != media["sha256"]:
            fail(f"production: storyboard media hash mismatch: {board['board_id']}")
        required_text = [item["content"] for item in board["required_text"]]
        approval_errors = verify_storyboard_text_approval(run_dir, media["media_revision_id"], required_text)
        if approval_errors:
            fail(f"production: storyboard {board['board_id']}: {'; '.join(approval_errors)}")
    validate_video_prompts(run_dir)
    story_path = outputs(run_dir) / "story.md"
    story_text = story_path.read_text(encoding="utf-8")
    if "## 商业信息" not in story_text:
        fail("production: story.md missing '## 商业信息' section")
    ok("production level")


def validate_delivery_level(run_dir: Path) -> None:
    validate_production_level(run_dir)
    final = validate_schema_file(outputs(run_dir) / "final_package_manifest.json", "final_package_manifest.schema.json")
    if final.get("status") != "completed" or final.get("blocking_issues"):
        fail(f"delivery: final package status is {final.get('status')}")
    for row in final["files"]:
        try:
            path = resolve_in_run(run_dir, row["path"], must_exist=True)
        except ValueError as exc:
            fail(str(exc))
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if path.stat().st_size != row["size"] or actual != row["sha256"]:
            fail(f"delivery: package integrity mismatch: {row['path']}")
    ok("delivery level")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a short-video local run.")
    parser.add_argument("run_dir")
    parser.add_argument("--level", choices=["structure", "draft", "production", "delivery"])
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
            "assets",
            "asset_executor",
            "asset_prompt_generation",
            "asset_prompts",
            "storyboard_prompt_generation",
            "storyboard_prompts",
            "video_segment_plan",
            "video_prompts",
            "video",
            "all",
        ],
    )
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    if args.level:
        {"structure": validate_structure_level, "draft": validate_draft_level, "production": validate_production_level, "delivery": validate_delivery_level}[args.level](run_dir)
        print("VALIDATION PASSED")
        return
    phase = PHASE_ALIASES.get(args.phase, args.phase)
    validators = {
        "initialized": validate_initialized,
        "story": validate_story,
        "art": validate_art,
        "storyboard": validate_storyboard,
        "assets": validate_assets,
        "asset_prompt_generation": validate_asset_prompt_generation,
        "storyboard_prompt_generation": validate_storyboard_prompt_generation,
        "video_segment_plan": validate_video_segment_plan,
        "video_prompts": validate_video_prompts,
        "all": validate_all,
    }
    validators[phase](run_dir)
    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()
