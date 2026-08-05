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

## 创意审查回环（idea_generation）

`idea_generation` 产出 `brief.md` + `story.md` 后、人工审批前，运行 `advertising-idea-review` 自动审查：

1. 审查 skill 读取 `outputs/brief.md` + `outputs/story.md`，在对话中输出八维诊断报告（世界规则 / 致命 / 重要 / 一般 / 值得保留 / 优先修改顺序），并把问题清单写入 `outputs/idea_review_feedback.md`。
2. 审查**只出意见、不放行**。人工据此决定：`approve` 放行，或 `reject` 进入修订轮。
3. 修订轮：`advertising-idea-strategy` 自动读取 `outputs/idea_review_feedback.md` 逐条修订，产出新 `brief.md` + `story.md`（新 Artifact Revision，旧版保留快照）。
4. 修订后**不自动二次审查**，由人工直接放行；仅当人工明确要求时才再次运行审查（审查轮次 +1）。

`outputs/idea_review_feedback.md` 是流程状态文件：不进 Artifact/Approval Registry、不进最终包、不参与 `validate_project.py` 校验。

项目未声明视频画幅时使用 `16:9`。该值必须在 Board Packet、Video Prompt Manifest、提示词正文和最终包中一致。
