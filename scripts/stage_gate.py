"""Artifact checks used before a pipeline stage can complete or be approved."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from artifact_runtime import digest_path, verify_artifact_revision
from path_safety import resolve_in_run
from pipeline_spec import REPO_ROOT, stage_map


def read(path: Path):
    if not path.is_file():
        raise ValueError(f"missing required artifact: {path}")
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".wav"}:
        return path
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8-sig"))
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"artifact is empty: {path}")
    return text


def validate_stage_outputs(run: Path, stage: str, approving: bool = False) -> None:
    out = run / "outputs"
    for declared in stage_map()[stage].get("outputs", []):
        path = resolve_in_run(run, declared["path"], must_exist=True)
        value = read(path)
        schema_name = declared.get("schema")
        if schema_name:
            schema = json.loads((REPO_ROOT / "schemas" / schema_name).read_text(encoding="utf-8-sig"))
            errors = list(Draft202012Validator(schema).iter_errors(value))
            if errors:
                raise ValueError(f"{path.name}: {errors[0].message}")
    if stage == "idea_generation":
        read(out / "brief.md"); read(out / "story.md")
    elif stage == "art_direction":
        read(out / "style_bible.md")
    elif stage == "storyboard_director":
        read(out / "storyboard.json")
    elif stage == "asset_executor":
        asset_plan = read(out / "asset_manifest.json")
        read(out / "shot_asset_map.json")
        _check_asset_reference_layouts(asset_plan)
    elif stage == "asset_prompt_generation":
        manifest = read(out / "asset_prompt_manifest.json")
        for prompt in manifest["prompts"]:
            path = resolve_in_run(run, prompt["prompt_path"], must_exist=True)
            read(path)
            if digest_path(path) != prompt["sha256"]:
                raise ValueError(f"asset prompt hash mismatch: {prompt['asset_id']}")
    elif stage == "asset_image_generation":
        plan = read(out / "asset_manifest.json")
        results = read(out / "asset_media_manifest.json")
        expected = {item["asset_id"] for group in ("characters", "scenes", "props") for item in plan.get(group, []) if item.get("generation_required")}
        actual = {row["asset_id"] for row in results["media"]}
        missing = sorted(expected - actual)
        if missing:
            raise ValueError("asset media incomplete: " + ", ".join(missing))
        for result in results["media"]:
            errors = verify_artifact_revision(run, result["media_revision_id"])
            if errors:
                raise ValueError("; ".join(errors))
    elif stage == "video_segment_planning":
        read(out / "video_segment_plan.json")
    elif stage == "storyboard_prompt_generation":
        manifest = read(out / "storyboard_board_manifest.json")
        storyboard = read(out / "storyboard.json")
        shots = {row["shot_id"]: row for row in storyboard["shots"]}
        if not manifest.get("boards"):
            raise ValueError("storyboard board manifest has no boards")
        for board in manifest["boards"]:
            read(resolve_in_run(run, board["packet_path"], must_exist=True))
            prompt = resolve_in_run(run, board["prompt_path"], must_exist=True)
            read(prompt)
            if not board.get("prompt_hash") or digest_path(prompt) != board["prompt_hash"]:
                raise ValueError(f"storyboard prompt hash mismatch: {board['board_id']}")
            expected_text = [
                {"shot_id": shot_id, **item}
                for shot_id in board["shot_ids"]
                for item in shots[shot_id]["advertising_text"]
            ]
            if board["required_text"] != expected_text:
                raise ValueError(f"storyboard text contract mismatch: {board['board_id']}")
            prompt_text = prompt.read_text(encoding="utf-8")
            for item in expected_text:
                if item["content"] not in prompt_text:
                    raise ValueError(f"storyboard prompt omits advertising text: {board['board_id']} {item['content']}")
            if expected_text and ("无文字" in prompt_text or "不出现任何文字" in prompt_text):
                raise ValueError(f"storyboard prompt forbids declared text: {board['board_id']}")
    elif stage == "storyboard_image_generation":
        plan = read(out / "storyboard_board_manifest.json")
        results = read(out / "storyboard_media_manifest.json")
        expected = {row["board_id"] for row in plan["boards"]}
        actual = {row["board_id"] for row in results["media"]}
        missing = sorted(expected - actual)
        if missing:
            raise ValueError("storyboard media incomplete: " + ", ".join(missing))
        for result in results["media"]:
            read(resolve_in_run(run, result["media_path"], must_exist=True))
            errors = verify_artifact_revision(run, result["media_revision_id"])
            if errors:
                raise ValueError("; ".join(errors))
    elif stage == "video_prompt_generation":
        manifest = read(out / "video_prompt_manifest.json")
        asset_plan = read(out / "asset_manifest.json")
        board_plan = read(out / "storyboard_board_manifest.json")
        required_text_by_video = {}
        for board in board_plan["boards"]:
            required_text_by_video.setdefault(board["video_id"], []).extend(
                item["content"] for item in board["required_text"]
            )
        scene_names = [row["asset_name"] for row in asset_plan.get("scenes", [])]
        non_product_names = [
            row["asset_name"] for row in asset_plan.get("props", [])
            if row.get("business_role") != "advertised_product"
        ]
        if not manifest.get("videos"):
            raise ValueError("video prompt manifest has no videos")
        for video in manifest["videos"]:
            prompt = resolve_in_run(run, video["prompt_path"], must_exist=True)
            read(prompt)
            if digest_path(prompt) != video["prompt_hash"]:
                raise ValueError(f"video prompt hash mismatch: {video['video_id']}")
            prompt_text = prompt.read_text(encoding="utf-8")
            if video["aspect_ratio"] not in prompt_text:
                raise ValueError(f"video prompt omits aspect ratio: {video['video_id']}")
            forbidden = [name for name in scene_names + non_product_names if f"@{name}" in prompt_text]
            if forbidden:
                raise ValueError(f"video prompt references forbidden assets: {', '.join(forbidden)}")
            if required_text_by_video.get(video["video_id"]):
                if "保持分镜板中已经出现的广告文字" not in prompt_text or "禁止新增文字" not in prompt_text:
                    raise ValueError(f"video prompt omits locked advertising-text constraints: {video['video_id']}")
                if "无文字" in prompt_text or "不出现任何文字" in prompt_text:
                    raise ValueError(f"video prompt conflicts with board advertising text: {video['video_id']}")
    elif stage == "final_package":
        final = read(out / "final_package_manifest.json")
        if final.get("status") != "completed":
            raise ValueError("final package is not completed")


# 各资产类型强制参考图画幅约定（键用 asset_manifest.json 的 schema 组名复数）：
# - characters: 21:9 转面四视图（character_turnaround_21x9_v1）
# - scenes: 16:9 Key Plate + 四宫格（scene_keyplate_quad_v1）
# - props: 16:9 单参考图（prop_single_reference_v1）
_REFERENCE_LAYOUT_BY_TYPE = {
    "characters": "character_turnaround_21x9_v1",
    "scenes": "scene_keyplate_quad_v1",
    "props": "prop_single_reference_v1",
}


def _check_asset_reference_layouts(asset_plan: dict) -> None:
    """Hard-gate the asset-reference aspect-ratio contract at the asset_executor gate."""
    for group, expected in _REFERENCE_LAYOUT_BY_TYPE.items():
        for item in asset_plan.get(group, []) or []:
            name = item.get("asset_name", "?")
            layout = item.get("reference_layout")
            if item.get("generation_required") is True and layout != expected:
                raise ValueError(
                    f"{group} 资产 {name} 必须使用参考图约定 {expected}"
                    f"（对应画幅 {'21:9' if '21x9' in expected else '16:9'}），当前为 {layout!r}"
                )
            if group == "props" and item.get("business_role") == "advertised_product" and layout != expected:
                raise ValueError(f"广告商品 {name} 必须使用参考图约定 {expected}，当前为 {layout!r}")
