from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from artifact_runtime import (
    approve_artifact_revision, approve_stage_artifacts, register_media_artifact,
    register_stage_artifacts, verify_artifact_approval, verify_storyboard_text_approval,
    verify_stage_integrity,
)
from path_safety import resolve_in_run
from pipeline_runtime import APPROVAL_REQUIRED, SKIPPABLE, STAGES
from pipeline_spec import load_pipeline_spec, resolve_skill_path, stage_map


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PipelineSpecTests(unittest.TestCase):
    def test_config_is_single_source_of_stage_behavior(self):
        spec = load_pipeline_spec()
        self.assertEqual(STAGES, [row["id"] for row in spec["stages"]])
        self.assertIn("storyboard_director", APPROVAL_REQUIRED)
        self.assertIn("asset_image_generation", SKIPPABLE)
        self.assertEqual(stage_map()["video_segment_planning"]["depends_on"], ["asset_executor"])

    def test_draft_only_media_skip_blocks_final_package_readiness(self):
        checkpoint = json.loads((ROOT / "examples" / "minimal_run" / "checkpoint.json").read_text(encoding="utf-8"))
        from pipeline_runtime import ready_stages
        self.assertNotIn("final_package", ready_stages(ROOT / "examples" / "minimal_run", checkpoint))

    def test_sequence_review_is_required_before_asset_executor(self):
        # storyboard_sequence_review 是 asset_executor 的必需前置阶段。
        from pipeline_runtime import STAGES
        self.assertIn("storyboard_sequence_review", STAGES)
        self.assertEqual(stage_map()["storyboard_sequence_review"]["depends_on"], ["storyboard_director"])
        self.assertIn("storyboard_sequence_review", stage_map()["asset_executor"]["depends_on"])
        self.assertTrue(resolve_skill_path("storyboard-sequence-review").is_file())
        # review 未完成时 asset_executor 不应 ready
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(ROOT / "examples" / "minimal_run", run)
            from pipeline_runtime import ready_stages
            checkpoint = json.loads((run / "checkpoint.json").read_text(encoding="utf-8"))
            checkpoint["stages"]["storyboard_sequence_review"] = {"status": "not_started", "version": 0, "updated_at": None}
            checkpoint["stages"]["asset_executor"] = {"status": "not_started", "version": 0, "updated_at": None}
            checkpoint["blockers"] = []
            (run / "checkpoint.json").write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
            ready = ready_stages(run, checkpoint)
            self.assertNotIn("asset_executor", ready)
            # review 完成后放行
            checkpoint = json.loads((run / "checkpoint.json").read_text(encoding="utf-8"))
            checkpoint["stages"]["storyboard_sequence_review"] = {"status": "completed", "version": 1, "updated_at": "2026-07-31T00:00:00Z"}
            (run / "checkpoint.json").write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
            ready = ready_stages(run, checkpoint)
            self.assertIn("asset_executor", ready)

    def test_sequence_review_p0_blocks_validation(self):
        # review 存在且含未解决 P0 时，structure 校验必须拦截
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(ROOT / "examples" / "minimal_run", run)
            review_path = run / "outputs" / "reviews" / "storyboard_sequence_review.json"
            self.assertTrue(review_path.is_file())
            review = json.loads(review_path.read_text(encoding="utf-8"))
            review["status"] = "revise_required"
            review["issues"] = [{
                "severity": "P0", "category": "shot_boundary", "shot_ids": ["S001"],
                "description": "硬拆", "fix_suggestion": "合并",
            }]
            review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "validate_project.py"), str(run), "--level", "structure"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unresolved P0", result.stdout)

    def test_all_referenced_skills_resolve_once(self):
        for name in [
            "advertising-idea-strategy", "advertising-art-direction",
            "advertising-storyboard-strategy", "plan-ad-assets",
            "generate-storyboard-prompts", "generate-video-prompts",
            "storyboard-sequence-review",
        ]:
            self.assertTrue(resolve_skill_path(name).is_file())

    def test_idea_review_skill_resolves_and_is_not_reported_as_orphan(self):
        # advertising-idea-review is invoked by run-ad-pipeline before idea_generation
        # approval, never by a stage executor, so the contract validator must not
        # flag it as an orphan skill.
        self.assertTrue(resolve_skill_path("advertising-idea-review").is_file())
        result = subprocess.run([sys.executable, str(SCRIPTS / "validate_pipeline_contract.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("orphan", result.stdout)

    def test_idea_strategy_revision_mode_is_wired_to_feedback_file(self):
        # Revision rounds must read outputs/idea_review_feedback.md instead of
        # generating from scratch; both the skill wrapper and the source prompt
        # must reference it.
        strategy_skill = (ROOT / ".agents" / "skills" / "advertising-idea-strategy" / "SKILL.md").read_text(encoding="utf-8")
        source = (ROOT / "skills" / "raw_prompts" / "idea_generation.source.md").read_text(encoding="utf-8")
        self.assertIn("idea_review_feedback.md", strategy_skill)
        self.assertIn("idea_review_feedback.md", source)

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                resolve_in_run(Path(temp), "../outside.txt")

    def test_video_segment_duration_boundaries_are_4_to_30(self):
        schema = json.loads((ROOT / "schemas" / "video_segment_plan.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)

        def payload(duration: float) -> dict:
            return {"segments": [{
                "video_id": "V001", "source_shots": ["S001"], "scene_id": "SC001",
                "duration_seconds": duration, "merge_strategy": "single_shot",
                "merge_reason": "boundary test", "frame_plan": [{"shot_id": "S001", "role": "first_frame"}],
            }]}

        self.assertTrue(list(validator.iter_errors(payload(3.99))))
        self.assertEqual(list(validator.iter_errors(payload(4))), [])
        self.assertEqual(list(validator.iter_errors(payload(30))), [])
        self.assertTrue(list(validator.iter_errors(payload(30.01))))

    def test_default_video_aspect_ratio_is_16_by_9(self):
        spec = load_pipeline_spec()
        self.assertEqual(spec["production_defaults"]["video_aspect_ratio"], "16:9")
        checkpoint = json.loads((ROOT / "checkpoint.template.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["ad_production"]["aspect_ratio"], "16:9")


class ArtifactApprovalTests(unittest.TestCase):
    def test_approval_becomes_invalid_after_canonical_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / "outputs").mkdir()
            (run / "outputs" / "brief.md").write_text("brief", encoding="utf-8")
            (run / "outputs" / "story.md").write_text("story", encoding="utf-8")
            checkpoint = {"stages": {name: {"status": "not_started"} for name in STAGES}}
            ids = register_stage_artifacts(run, checkpoint, "idea_generation")
            checkpoint["stages"]["idea_generation"].update({"status": "review_required", "artifact_revision_ids": ids})
            approvals = approve_stage_artifacts(run, checkpoint, "idea_generation", "tester", "approved fixture")
            self.assertEqual(len(approvals), 2)
            self.assertEqual(verify_stage_integrity(run, checkpoint, "idea_generation"), [])
            (run / "outputs" / "story.md").write_text("changed", encoding="utf-8")
            errors = verify_stage_integrity(run, checkpoint, "idea_generation")
            self.assertTrue(any("modified after registration" in error for error in errors))

    def test_start_invalidates_hash_changed_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp); (run / "outputs").mkdir(); (run / "inputs").mkdir()
            (run / "outputs" / "brief.md").write_text("brief", encoding="utf-8")
            (run / "outputs" / "story.md").write_text("story", encoding="utf-8")
            checkpoint = {
                "schema_version": "8.0",
                "phase_order": STAGES,
                "stages": {name: {"status": "not_started", "version": 0, "updated_at": None} for name in STAGES},
                "blockers": [],
            }
            ids = register_stage_artifacts(run, checkpoint, "idea_generation")
            checkpoint["stages"]["idea_generation"].update({"status": "review_required", "artifact_revision_ids": ids})
            checkpoint["stages"]["idea_generation"]["approval_ids"] = approve_stage_artifacts(run, checkpoint, "idea_generation", "tester", "ok")
            checkpoint["stages"]["idea_generation"]["status"] = "approved"
            write_json(run / "checkpoint.json", checkpoint)
            (run / "outputs" / "story.md").write_text("tampered", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPTS / "run_pipeline.py"), str(run), "start", "--stage", "art_direction"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            saved = json.loads((run / "checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["stages"]["idea_generation"]["status"], "invalidated")
            self.assertTrue(any("modified after registration" in row["message"] for row in saved["blockers"]))

    def test_media_approval_becomes_invalid_after_file_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp); media = run / "outputs" / "assets" / "image.v001.png"
            media.parent.mkdir(parents=True); media.write_bytes(b"approved-image")
            row = register_media_artifact(run, artifact_name="asset-media.character.test", stage="asset_image_generation", source=media)
            approve_artifact_revision(run, row["artifact_revision_id"], "tester", "ok")
            self.assertEqual(verify_artifact_approval(run, row["artifact_revision_id"]), [])
            media.write_bytes(b"modified-image")
            self.assertTrue(any("modified after registration" in error for error in verify_artifact_approval(run, row["artifact_revision_id"])))


class ManifestAndPackageTests(unittest.TestCase):
    def test_board_packet_builder_preserves_v_sb_s_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(ROOT / "examples" / "minimal_run", run)
            result = subprocess.run([sys.executable, str(SCRIPTS / "build_storyboard_packets.py"), str(run)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            manifest = json.loads((run / "outputs" / "storyboard_board_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["boards"][0]["video_id"], "V001")
            self.assertEqual(manifest["boards"][0]["shot_ids"], ["S001", "S002"])

    def test_package_uses_explicit_board_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp); out = run / "outputs"
            (out / "video_prompts").mkdir(parents=True)
            (out / "storyboard_boards").mkdir(parents=True)
            for video_id in ("V001", "V002"):
                (out / "video_prompts" / f"{video_id}.md").write_text(f"prompt {video_id}", encoding="utf-8")
            for board_id in ("SB001", "SB002"):
                (out / "storyboard_boards" / f"{board_id}.png").write_bytes(b"image-" + board_id.encode())
            write_json(out / "asset_manifest.json", {
                "characters": [{"asset_id": "character.hero.base", "asset_name": "主角", "canonical_name": "主角", "asset_type": "character", "generation_required": True}],
                "scenes": [{"asset_id": "scene.room.base", "asset_name": "房间场景", "canonical_name": "房间场景", "asset_type": "scene", "generation_required": True}],
                "props": [
                    {"asset_id": "prop.product.base", "asset_name": "广告商品", "canonical_name": "广告商品", "asset_type": "prop", "business_role": "advertised_product", "generation_required": True},
                    {"asset_id": "prop.cup.base", "asset_name": "杯子", "canonical_name": "杯子", "asset_type": "prop", "business_role": "story_prop", "generation_required": False},
                ],
            })
            asset_media_rows = []
            for asset_id in ("character.hero.base", "scene.room.base", "prop.product.base"):
                media_path = out / "assets" / f"{asset_id}.png"
                media_path.parent.mkdir(parents=True, exist_ok=True)
                media_path.write_bytes(b"asset-" + asset_id.encode())
                artifact = register_media_artifact(run, artifact_name=f"asset-media.{asset_id}", stage="asset_image_generation", source=media_path)
                approve_artifact_revision(run, artifact["artifact_revision_id"], "tester", "ok")
                asset_media_rows.append({"asset_id": asset_id, "revision": 1, "media_revision_id": artifact["artifact_revision_id"], "media_path": f"./outputs/assets/{asset_id}.png", "sha256": artifact["sha256"]})
            write_json(out / "asset_media_manifest.json", {"schema_version": "1.0", "media": asset_media_rows})
            media_rows = []
            for board_id in ("SB001", "SB002"):
                artifact = register_media_artifact(run, artifact_name=f"storyboard-media.{board_id}", stage="storyboard_image_generation", source=out / "storyboard_boards" / f"{board_id}.png")
                approve_artifact_revision(
                    run, artifact["artifact_revision_id"], "tester", "ok",
                    evidence={"text_verification": {
                        "declared_text": [], "verified_text": [],
                        "exact_match": True, "extra_text_absent": True,
                    }},
                )
                media_rows.append({"board_id": board_id, "revision": 1, "media_revision_id": artifact["artifact_revision_id"], "media_path": f"./outputs/storyboard_boards/{board_id}.png", "sha256": artifact["sha256"]})
            write_json(out / "storyboard_media_manifest.json", {"schema_version": "1.0", "media": media_rows})
            write_json(out / "storyboard_board_manifest.json", {
                "schema_version": "2.0",
                "boards": [
                    {"board_id": "SB001", "video_id": "V001", "shot_ids": ["S001"], "duration_seconds": 5, "required_text": [], "packet_path": "./outputs/storyboard_board_inputs/SB001.json", "prompt_path": "./outputs/storyboard_boards/SB001.md", "prompt_hash": None},
                    {"board_id": "SB002", "video_id": "V002", "shot_ids": ["S002"], "duration_seconds": 5, "required_text": [], "packet_path": "./outputs/storyboard_board_inputs/SB002.json", "prompt_path": "./outputs/storyboard_boards/SB002.md", "prompt_hash": None},
                ],
            })
            write_json(out / "video_prompt_manifest.json", {
                "schema_version": "2.0",
                "videos": [
                    {"video_id": "V001", "source_shots": ["S001"], "source_boards": ["SB001"], "duration_seconds": 5, "aspect_ratio": "16:9", "prompt_path": "./outputs/video_prompts/V001.md", "prompt_hash": "sha256:" + hashlib.sha256(b"prompt V001").hexdigest(), "character_assets": ["主角"], "product_assets": ["广告商品"]},
                    {"video_id": "V002", "source_shots": ["S002"], "source_boards": ["SB002"], "duration_seconds": 5, "aspect_ratio": "16:9", "prompt_path": "./outputs/video_prompts/V002.md", "prompt_hash": "sha256:" + hashlib.sha256(b"prompt V002").hexdigest(), "character_assets": ["主角"], "product_assets": ["广告商品"]},
                ],
            })
            result = subprocess.run([sys.executable, str(SCRIPTS / "package_production.py"), str(run), "--mode", "portable"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            final = json.loads((out / "final_package_manifest.json").read_text(encoding="utf-8"))
            root = resolve_in_run(run, final["package_root"], must_exist=True)
            v1 = json.loads((root / "videos" / "V001" / "segment.json").read_text(encoding="utf-8"))
            v2 = json.loads((root / "videos" / "V002" / "segment.json").read_text(encoding="utf-8"))
            self.assertEqual([x["id"] for x in v1["references"] if x["role"] == "storyboard_board"], ["SB001"])
            self.assertEqual([x["id"] for x in v2["references"] if x["role"] == "storyboard_board"], ["SB002"])
            self.assertEqual(v1["aspect_ratio"], "16:9")
            self.assertFalse(any(x["role"] in {"scene", "prop"} for x in v1["references"] + v2["references"]))
            self.assertEqual({x["role"] for x in v1["references"]}, {"video_prompt", "storyboard_board", "character", "product"})

    def test_board_rebuild_does_not_touch_media_results(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(ROOT / "examples" / "minimal_run", run)
            media_manifest = {"schema_version": "1.0", "media": [{"board_id": "SB001", "revision": 1, "media_revision_id": "storyboard-media.SB001:r001", "media_path": "./outputs/storyboard_boards/SB001.v001.png", "sha256": "sha256:" + "a" * 64}]}
            write_json(run / "outputs" / "storyboard_media_manifest.json", media_manifest)
            result = subprocess.run([sys.executable, str(SCRIPTS / "build_storyboard_packets.py"), str(run)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(json.loads((run / "outputs" / "storyboard_media_manifest.json").read_text(encoding="utf-8")), media_manifest)

    def test_video_manifest_allows_only_characters_and_advertised_products(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(ROOT / "examples" / "minimal_run", run)
            checkpoint = json.loads((run / "checkpoint.json").read_text(encoding="utf-8"))
            checkpoint["ad_production"]["aspect_ratio"] = None
            write_json(run / "checkpoint.json", checkpoint)
            assets = json.loads((run / "outputs" / "asset_manifest.json").read_text(encoding="utf-8"))
            assets["props"][0].update({"business_role": "advertised_product", "generation_required": True})
            write_json(run / "outputs" / "asset_manifest.json", assets)
            result = subprocess.run([sys.executable, str(SCRIPTS / "build_video_prompt_manifest.py"), str(run)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            video = json.loads((run / "outputs" / "video_prompt_manifest.json").read_text(encoding="utf-8"))["videos"][0]
            self.assertEqual(video["aspect_ratio"], "16:9")
            self.assertEqual(video["product_assets"], ["手机"])
            self.assertNotIn("scene_assets", video)
            self.assertNotIn("prop_assets", video)

    def test_advertising_text_propagates_and_requires_exact_board_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(ROOT / "examples" / "minimal_run", run)
            storyboard = json.loads((run / "outputs" / "storyboard.json").read_text(encoding="utf-8"))
            storyboard["shots"][1]["advertising_text"] = [{
                "content": "现在下单", "role": "cta", "placement": "画面下方中央",
                "presentation": "graphic_card", "must_match_exactly": True,
            }]
            write_json(run / "outputs" / "storyboard.json", storyboard)
            board_prompt = run / "outputs" / "storyboard_boards" / "SB001.md"
            board_prompt.write_text(board_prompt.read_text(encoding="utf-8") + "\n广告文字：现在下单，画面下方中央。\n", encoding="utf-8")
            built = subprocess.run([sys.executable, str(SCRIPTS / "build_storyboard_packets.py"), str(run)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr or built.stdout)
            board = json.loads((run / "outputs" / "storyboard_board_manifest.json").read_text(encoding="utf-8"))["boards"][0]
            self.assertEqual([row["content"] for row in board["required_text"]], ["现在下单"])

            source = Path(temp) / "board.png"
            source.write_bytes(b"board-with-exact-text")
            registered = subprocess.run([sys.executable, str(SCRIPTS / "register_storyboard_result.py"), str(run), "SB001", str(source)], capture_output=True, text=True)
            self.assertEqual(registered.returncode, 0, registered.stderr or registered.stdout)
            rejected = subprocess.run([sys.executable, str(SCRIPTS / "approve_media.py"), str(run), "board", "SB001", "--actor", "tester", "--confirm-no-extra-text"], capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            approved = subprocess.run([
                sys.executable, str(SCRIPTS / "approve_media.py"), str(run), "board", "SB001",
                "--actor", "tester", "--verified-text", "现在下单", "--confirm-no-extra-text",
            ], capture_output=True, text=True)
            self.assertEqual(approved.returncode, 0, approved.stderr or approved.stdout)
            media = json.loads((run / "outputs" / "storyboard_media_manifest.json").read_text(encoding="utf-8"))["media"][-1]
            self.assertEqual(verify_storyboard_text_approval(run, media["media_revision_id"], ["现在下单"]), [])

            video_prompt = run / "outputs" / "video_prompts" / "V001.md"
            video_prompt.write_text(
                video_prompt.read_text(encoding="utf-8")
                + "\n保持分镜板中已经出现的广告文字内容、位置和样式不变；禁止新增文字；无水印。\n",
                encoding="utf-8",
            )
            built_video = subprocess.run([sys.executable, str(SCRIPTS / "build_video_prompt_manifest.py"), str(run)], capture_output=True, text=True)
            self.assertEqual(built_video.returncode, 0, built_video.stderr or built_video.stdout)
            valid_video = subprocess.run([sys.executable, str(SCRIPTS / "validate_project.py"), str(run), "--phase", "video_prompts"], capture_output=True, text=True)
            self.assertEqual(valid_video.returncode, 0, valid_video.stdout + valid_video.stderr)

            video_prompt.write_text(video_prompt.read_text(encoding="utf-8").replace("禁止新增文字", "允许新增文字"), encoding="utf-8")
            subprocess.run([sys.executable, str(SCRIPTS / "build_video_prompt_manifest.py"), str(run)], check=True, capture_output=True, text=True)
            invalid_video = subprocess.run([sys.executable, str(SCRIPTS / "validate_project.py"), str(run), "--phase", "video_prompts"], capture_output=True, text=True)
            self.assertNotEqual(invalid_video.returncode, 0)
            self.assertIn("locked advertising-text constraints", invalid_video.stdout)


class EndToEndTests(unittest.TestCase):
    def test_production_delivery_and_media_tamper_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(ROOT / "examples" / "minimal_run", run)
            checkpoint = json.loads((run / "checkpoint.json").read_text(encoding="utf-8"))
            checkpoint["blockers"] = []

            for stage in ("idea_generation", "art_direction", "storyboard_director", "asset_executor", "asset_prompt_generation", "video_segment_planning", "storyboard_prompt_generation"):
                ids = register_stage_artifacts(run, checkpoint, stage)
                checkpoint["stages"][stage]["artifact_revision_ids"] = ids
                if stage in APPROVAL_REQUIRED:
                    checkpoint["stages"][stage]["status"] = "review_required"
                    checkpoint["stages"][stage]["approval_ids"] = approve_stage_artifacts(run, checkpoint, stage, "tester", "fixture")
                    checkpoint["stages"][stage]["status"] = "approved"
                else:
                    checkpoint["stages"][stage]["status"] = "completed"

            source = Path(temp) / "source.png"
            source.write_bytes(b"valid-image-fixture")
            for asset_id in ("character.lin-xiaoman.rainy-home", "scene.rainy-living-room.base"):
                result = subprocess.run([sys.executable, str(SCRIPTS / "import_generated_media.py"), str(run), asset_id, str(source)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
                result = subprocess.run([sys.executable, str(SCRIPTS / "approve_media.py"), str(run), "asset", asset_id, "--actor", "tester"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            checkpoint["stages"]["asset_image_generation"].update({"status": "completed", "artifact_revision_ids": register_stage_artifacts(run, checkpoint, "asset_image_generation")})

            result = subprocess.run([sys.executable, str(SCRIPTS / "register_storyboard_result.py"), str(run), "SB001", str(source)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            result = subprocess.run([sys.executable, str(SCRIPTS / "approve_media.py"), str(run), "board", "SB001", "--actor", "tester", "--confirm-no-extra-text"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            checkpoint["stages"]["storyboard_image_generation"].update({"status": "completed", "artifact_revision_ids": register_stage_artifacts(run, checkpoint, "storyboard_image_generation")})
            checkpoint["stages"]["video_prompt_generation"].update({"status": "completed", "artifact_revision_ids": register_stage_artifacts(run, checkpoint, "video_prompt_generation")})
            for stage in STAGES:
                checkpoint["stages"][stage].pop("skip_effect", None)
                checkpoint["stages"][stage].pop("skip_reason", None)
            write_json(run / "checkpoint.json", checkpoint)

            package = subprocess.run([sys.executable, str(SCRIPTS / "package_production.py"), str(run), "--mode", "portable"], capture_output=True, text=True)
            self.assertEqual(package.returncode, 0, package.stderr or package.stdout)
            checkpoint["stages"]["final_package"].update({"status": "completed", "artifact_revision_ids": register_stage_artifacts(run, checkpoint, "final_package")})
            write_json(run / "checkpoint.json", checkpoint)
            delivery = subprocess.run([sys.executable, str(SCRIPTS / "validate_project.py"), str(run), "--level", "delivery"], capture_output=True, text=True)
            self.assertEqual(delivery.returncode, 0, delivery.stdout + delivery.stderr)

            asset_media = json.loads((run / "outputs" / "asset_media_manifest.json").read_text(encoding="utf-8"))["media"][0]
            resolve_in_run(run, asset_media["media_path"], must_exist=True).write_bytes(b"tampered")
            self.assertTrue(any("modified after registration" in error for error in verify_stage_integrity(run, checkpoint, "asset_image_generation")))
            production = subprocess.run([sys.executable, str(SCRIPTS / "validate_project.py"), str(run), "--level", "production"], capture_output=True, text=True)
            self.assertNotEqual(production.returncode, 0)
            self.assertIn("canonical mismatch", production.stdout)

    def test_codex_task_completion_updates_task_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"; (run / "outputs").mkdir(parents=True); (run / "inputs").mkdir()
            init = subprocess.run([sys.executable, str(SCRIPTS / "init_checkpoint.py"), "--template", str(ROOT / "checkpoint.template.json"), "--output", str(run / "checkpoint.json"), "--slug", "task-sync", "--created-at", "2026-08-01T00:00:00Z", "--run-dir", str(run)], capture_output=True, text=True)
            self.assertEqual(init.returncode, 0, init.stderr or init.stdout)
            dispatched = subprocess.run([sys.executable, str(SCRIPTS / "pipeline_engine.py"), str(run), "run", "--stage", "idea_generation"], capture_output=True, text=True)
            self.assertEqual(dispatched.returncode, 0, dispatched.stderr or dispatched.stdout)
            (run / "outputs" / "brief.md").write_text("brief", encoding="utf-8")
            (run / "outputs" / "story.md").write_text("story", encoding="utf-8")
            completed = subprocess.run([sys.executable, str(SCRIPTS / "run_pipeline.py"), str(run), "complete", "--stage", "idea_generation"], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            task = json.loads(next((run / "outputs" / "tasks" / "idea_generation").glob("TASK-*.json")).read_text(encoding="utf-8"))
            self.assertEqual(task["status"], "completed")
            self.assertEqual(len(task["output_artifact_revisions"]), 2)


class ValidationLevelTests(unittest.TestCase):
    def test_ambiguous_phase_all_fails(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "validate_project.py"), str(ROOT / "examples" / "minimal_run"), "--phase", "all"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ambiguous and deprecated", result.stdout)


if __name__ == "__main__":
    unittest.main()
