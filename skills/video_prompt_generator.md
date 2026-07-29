# Skill: video_prompt_generator
**Version**: 3.0.0

## Source Prompt
`skills/raw_prompts/seedance_video_prompt.source.md`

## Purpose
在所有分镜参考图通过视觉审核后，按已批准的 `video_segment_plan.json` 循环生成视频提示词。每次只处理一个 `V###`。

本 Skill 只服务当前流水线生产，不处理视频编辑、视频延长、音频参考、多模态实验任务或轨道拼接。

## Inputs
```json
{
  "video_segment_plan_path": "./outputs/video_segment_plan.json",
  "video_id": "V001",
  "storyboard_json_path": "./outputs/storyboard.json",
  "shot_asset_map_path": "./outputs/shot_asset_map.json",
  "storyboard_prompt_paths": [],
  "storyboard_image_paths": [],
  "asset_reference_paths": [],
  "output_prompt_path": "./outputs/approved/video_generation/V001/prompt.txt",
  "output_manifest_path": "./outputs/approved/video_generation/V001/manifest.json"
}
```

不需要读取 `story.md`。视频阶段以导演分镜、分镜参考图提示词、分镜图和资产图为准。

## Outputs
```json
{
  "video_prompt_path": "./outputs/approved/video_generation/V001/prompt.txt",
  "video_manifest_path": "./outputs/approved/video_generation/V001/manifest.json"
}
```

## Production Prompt Rules

视频提示词必须遵守以下规则：

- 资产先声明，正文后引用。
- 正文资产名必须与声明区完全一致。
- 分镜图锁定构图时，不重复描述已锁定构图，只写画面演进。
- 人物资产锁定外观时，不重复描述人物外形，只补动作、表情、姿态和情绪。
- 场景资产锁定空间时，不重复描述环境全貌，只补主体行动、镜头运动和局部变化。
- 抽象词必须转译为可见画面或可听声音。
- 每个视频段只使用一种主运镜方式。
- 道具一般写入正文描述，不使用 `@PROP`。
- 结尾必须写防字幕、防 Logo、防水印约束。

## Merge Policy

合并结果由 `video_segment_plan.json` 锁定。本 Skill 不重新合并、拆分或更改帧角色。

相邻分镜只有同时满足以下条件，才允许合并为一个 `V###`：

1. `shot_id` 连续。
2. `scene_id` 相同。
3. 合并后 `duration_seconds` 总和 `<= {max_generated_clip_seconds}`。
4. 没有场景切换、时间跳跃或叙事空间切换。
5. 动作、情绪、站位或镜头推进可以自然连续。

单个分镜小于 {max_generated_clip_seconds} 秒不代表必须单独生成；如果同场景、动作连续、总时长不超过 {max_generated_clip_seconds} 秒，优先合并。

必须拆分：

- `scene_id` 不同。
- 合并后超过 {max_generated_clip_seconds} 秒。
- 时间或叙事空间跳跃。
- 动作不连续，合并后提示词含混。

## Frame Reference Policy

视频阶段根据最终合并结果确定每张分镜图的实际角色：

- 单个 `S###` 生成一个 `V###`：该分镜图作为 `first_frame`。
- 多个 `S###` 合并为一个 `V###`：第一个 source shot 是 `first_frame`。
- 多个 `S###` 合并为一个 `V###`：最后一个 source shot 是 `last_frame`。
- 中间 source shots 是 `keyframe`。

每条 `V###` 必须在 `video_prompts.json` 中写入 `frame_references`。

## Previous Storyboard Anchor

如果 `storyboard_prompts.md` 中某个 source shot 标记：

```text
uses_previous_storyboard_reference: true
reference_purpose: placement_anchor
```

且没有跨 `scene_id`，视频提示词应保留：

```text
参考@上一分镜_站位，保持人物空间关系、朝向和相对位置不变
```

该锚点只用于站位、朝向、空间比例和连续性。

## Required JSON Per V###

每个 `V###` 必须包含：

```json
{
  "video_id": "V001",
  "task_type": "pipeline_shot_generation",
  "source_shots": ["S001", "S002"],
  "duration_seconds": 10,
  "scene_id": "SC001",
  "merge_decision": {
    "strategy": "merged_strong_action_continuity",
    "reason": "同一场景内动作与站位连续，合并可减少漂移。",
    "continuity_risk": "high"
  },
  "frame_references": [],
  "declared_assets": [],
  "uses_previous_storyboard_anchor": true,
  "risk_notice_required": false,
  "prompt_cn": "..."
}
```

## Markdown Output Requirements

每条 `V###` 必须包含：

```markdown
【自检通过项】
【资产声明区】
【中文视频提示词】
```

自检项最多 6 条，必须具体说明：资产命名一致、锁补匹配、情绪/氛围具象化、运镜纯度、合并判断、约束条件。

## Quality Gate

- [ ] 每个 storyboard shot 都被且仅被一个 `V###` 覆盖。
- [ ] 合并的 source shots 连续。
- [ ] 合并的 source shots 同一 `scene_id`。
- [ ] 合并总时长 `<= {max_generated_clip_seconds}` 秒。
- [ ] 每条 `V###` 有 `merge_decision`。
- [ ] 每条 `V###` 有 `frame_references`。
- [ ] 每条提示词有资产声明区。
- [ ] 抽象词已转译为可见动作、光影、声音或空间关系。
- [ ] 每个视频段只使用一种主运镜方式。
- [ ] 不输出英文 Prompt。
