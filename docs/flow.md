# Workflow Contract v8.0

实际阶段、依赖、executor、审批、skip 和输出以 `config/pipeline.yaml` 为唯一事实源。

| Stage | Output contract | Gate |
|---|---|---|
| `idea_generation` | `brief.md`, `story.md` | human approval |
| `art_direction` | `style_bible.md` | human approval |
| `storyboard_director` | `storyboard.json` | human approval + explicit advertising text |
| `asset_executor` | `asset_manifest.json`, `shot_asset_map.json` | immutable plan + prop business role |
| `asset_prompt_generation` | `asset_prompt_manifest.json` | prompt hash coverage |
| `asset_image_generation` | `asset_media_manifest.json` | draft-skippable |
| `video_segment_planning` | `video_segment_plan.json` | exact shot coverage + 4–30 seconds |
| `storyboard_prompt_generation` | `storyboard_board_manifest.json` | exact V/SB/S/text mapping |
| `storyboard_image_generation` | `storyboard_media_manifest.json` | draft-skippable + text-verified approval |
| `video_prompt_generation` | `video_prompt_manifest.json` | one prompt per V###, Board/Character/Product only |
| `final_package` | `final_package_manifest.json` | delivery validation |

计划 Manifest 不保存媒体路径或审批状态。媒体 Manifest 通过 revision ID 连接 Artifact Registry，审批通过相同 revision ID 连接 Approval Registry。

```text
plan manifest -> media artifact revision -> media manifest -> approval registry -> package
```

任何哈希不一致都会阻止 Production 和 Delivery。

项目未声明视频画幅时使用 `16:9`。该值必须在 Board Packet、Video Prompt Manifest、提示词正文和最终包中一致。
