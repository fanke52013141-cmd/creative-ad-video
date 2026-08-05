# Local Run Notes

> 本目录是客户项目数据，位于框架仓库之外（或虽在 `local_runs/` 但被 .gitignore 忽略）。
> **不要把本目录的任何内容 `git add` 到框架仓库。** 产物只在本地/私有位置流转。

## Project

- Slug:
- Owner:
- Goal:
- References:
- Constraints:
- Video aspect ratio: `16:9` when unspecified
- Video unit duration: `4-30 seconds`

## Generation modes

- Asset images: `codex_builtin | external_manual`
- Storyboard images: `codex_builtin | external_manual`
- Video generation: external

## Stage log

| Stage | Status | Main output |
|---|---|---|
| idea_generation | pending | `brief.md`, `story.md` |
| art_direction | pending | `style_bible.md` |
| storyboard_director | pending | `storyboard.json` |
| storyboard_sequence_review | pending | `reviews/storyboard_sequence_review.json` |
| asset_executor | pending | `asset_manifest.json`, `shot_asset_map.json` |
| asset_prompt_generation | pending | `asset_prompt_manifest.json` |
| asset_image_generation | draft-skippable | `asset_media_manifest.json` |
| video_segment_planning | pending | `video_segment_plan.json` |
| storyboard_prompt_generation | pending | `storyboard_board_manifest.json` |
| storyboard_image_generation | draft-skippable | `storyboard_media_manifest.json` |
| video_prompt_generation | pending | `video_prompt_manifest.json` |
| final_package | pending | `final_package_manifest.json` |

## Media rules

1. Do not modify an upstream plan Manifest when media is generated.
2. Register assets with `register_image_result.py` and boards with `register_storyboard_result.py`.
3. Approve the resulting Artifact Revision with `approve_media.py`.
4. A new result creates a new revision; never overwrite a prior media file.
5. Production requires the latest required media revision to have a matching hash-bound approval.
6. Board approval requires `--confirm-no-extra-text`; repeat `--verified-text` for every declared advertising string.
7. Video-model references are limited to boards, characters and advertised products.

## Validation

```text
python scripts/validate_project.py RUN_DIR --level draft
python scripts/validate_project.py RUN_DIR --level production
python scripts/validate_project.py RUN_DIR --level delivery
```

## Problems found

- Symptom:
- Failed stage:
- Root cause:
- Reusable fix target:
