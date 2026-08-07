# Workflow Contract v8.0

实际阶段、依赖、executor、审批、skip 和输出以 `config/pipeline.yaml` 为唯一事实源。

| Stage | Output contract | Gate |
|---|---|---|
| `idea_generation` | `brief.md`, `story.md` | human approval + creative review（自动审查意见，人工放行） |
| `art_direction` | `style_bible.md` | human approval |
| `storyboard_director` | `storyboard.json` | human approval + explicit advertising text |
| `storyboard_sequence_review` | `reviews/storyboard_sequence_review.json` | no unresolved P0（镜头边界/时长/抽象词审查） |
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

## DAG、审查回环与生成规则

完整的 DAG 图、创意审查回环、Skip 规则、V8 视频生成规则（含未声明画幅时使用 `16:9`）和回退规则，统一见 `PIPELINE_FLOW.md`，不在本文件重复维护。本文件只维护上表的阶段-产物-Gate 契约。
