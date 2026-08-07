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

## 质量门阻塞等级

| 阶段 | 必须通过的门槛 | 阻塞等级 |
|---|---|---|
| Idea Brief | 核心想法、时长、类型、限制不为空 | P0 |
| Story | 剧本可读、人物动机清楚、总时长匹配项目广告时长；不得输出 `story.json` | P0 |
| Creative Review | 运行 `advertising-idea-review`：八维审查、输出分级意见。只出意见不放行；修订后不自动重审 | P1（建议） |
| Art Direction | 用户视觉方向优先；`style_bible.md` 只含画面风格、色调、光线、AI 视觉执行要求 | P1 |
| Storyboard | 每个 shot 有时长、动作、构图/景别/镜头及 `advertising_text`；广告文字不得后补 | P0 |
| Asset Manifest | 人物只按持续可见变化拆变体；每个 Prop 声明 business_role；映射资产全部存在 | P0 |
| Character Assets | 一个人物状态资产输出一份 21:9 人物资产图提示词 | P1 / final P0 |
| Scene Assets | 核心空间结构明确；普通时间、光线、天气变化不拆新场景 | P1 |
| Prop Assets | 广告商品必须独立生成；普通剧情道具只进分镜板，不作视频参考 | P1 |
| Asset Image Generation | 每个 task 只生成一张图片；人物资产图允许 21:9 多视角单图 | P0 |
| Storyboard Prompts | 每个 shot 被一个 Board 覆盖；frame role 与视频段一致 | P0 |
| Storyboard Image Generation | 每个 `SB###` 生成一张分镜板长图；审批逐字核验声明文字 | P0 |
| Video Prompts | 每个 `V###` 为 4–30 秒，显式声明画幅（默认 16:9）；只引用 Board/Character/Product | P0 |
| Final Handoff | 按 Manifest 交付 video prompts、Boards、人物和广告商品参考 | P0 |

## 阶段状态机

| 状态 | 含义 | 满足依赖 |
|---|---|---|
| `not_started` | 尚未开始 | 否 |
| `in_progress` | 正在执行 | 否 |
| `review_required` | Artifact 已注册，等待审批 | 否 |
| `approved` | 当前 revision/hash 已批准 | 是 |
| `completed` | 无审批阶段完成 | 是 |
| `skipped` | 配置允许且已记录原因 | 是，但 `draft_only` 不能通过 production |
| `failed` | 执行失败，可重试 | 否 |
| `blocked` | 存在不可继续的问题 | 否 |
| `invalidated` | 上游 revision 变化导致失效 | 否 |

规则：依赖来自 PipelineSpec 的 `depends_on`；`ready` 是动态调度结果不写入 status；Approval 必须绑定 Artifact Revision + SHA-256；Board Approval 还须绑定广告文字逐字匹配；`invalidate` 沿 DAG 递归传播；`completed_with_known_gaps` 不再作为阶段终态。
