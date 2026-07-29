# Video Prompt Generation Protocol

本协议覆盖当前主流程的 `video_prompt_generator`。旧的 `outputs/05_video_prompts/shots/SHOT_XXX.md` 逐 shot 文件结构已废弃；当前主流程只要求输出：

```text
outputs/video_prompts.md
outputs/video_prompts.json
```

## 输入

```json
{
  "storyboard_json_path": "./outputs/storyboard.json",
  "storyboard_prompts_path": "./outputs/storyboard_prompts.md",
  "storyboard_reference_dir": "./outputs/storyboards",
  "shot_asset_map_path": "./outputs/shot_asset_map.json",
  "asset_reference_dir": "./outputs/assets"
}
```

## 输出

### Markdown

`outputs/video_prompts.md` 是给即梦 / Seedance 复制使用的中文提示词文档。每个 `V###` 必须包含：

```markdown
## V001
- 来源分镜：S001-S002
- 时长：10s
- 任务类型：pipeline_shot_generation
- 分镜角色：S001=首帧，S002=尾帧
- 合并判断：...

一、【自检通过项】
...

二、【资产声明区】
@S001_分镜参考图（首帧）
@S002_分镜参考图（尾帧）
@林小满_雨夜居家装（人物资产）
@雨夜客厅场景（场景资产）

三、【中文视频提示词】
...
```

### JSON

`outputs/video_prompts.json` 是机器可校验的生产计划。每个 `V###` 必须包含：

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
  "frame_references": [
    {
      "shot_id": "S001",
      "asset_name": "S001_分镜参考图",
      "role": "first_frame",
      "path": "outputs/storyboards/S001.png"
    }
  ],
  "declared_assets": [],
  "uses_previous_storyboard_anchor": true,
  "risk_notice_required": false,
  "prompt_cn": "..."
}
```

## 合并规则

合并对象是连续 `S###`，不是 `SC###`。`SC###` 只是合并边界。

相邻分镜只有同时满足以下条件，才允许合并为一个 `V###`：

1. `shot_id` 连续且顺序一致。
2. `scene_id` 相同。
3. 合并后 `duration_seconds` 总和 `<= {max_generated_clip_seconds}`。
4. 没有场景切换、时间跳跃或叙事空间切换。
5. 动作、情绪、站位或镜头推进可以自然连续。

必须拆分：

- `scene_id` 不同。
- 合并后超过 {max_generated_clip_seconds} 秒。
- 时间或叙事空间跳跃。
- 动作不连续，合并后提示词含混。

## 分镜图角色

视频阶段根据最终合并结果确定每张分镜图的实际角色：

- 单个 `S###` 生成一个 `V###`：该分镜图作为 `first_frame`。
- 多个 `S###` 合并为一个 `V###`：第一个 source shot 是 `first_frame`。
- 多个 `S###` 合并为一个 `V###`：最后一个 source shot 是 `last_frame`。
- 中间 source shots 是 `keyframe`。

每条 `V###` 必须在 `video_prompts.json.frame_references` 中记录这些角色。

## 资产引用规则

- 分镜图使用 `@S001_分镜参考图` 这类具体名称。
- 人物使用 `asset_manifest.json` 中固定的人物或持续变体资产名，例如 `@林小满_雨夜居家装`。
- 场景使用 `asset_manifest.json` 中固定的场景资产名，例如 `@雨夜客厅场景`。
- 道具默认不使用 `@PROP`，而是在正文中自然描述。
- 正文引用名必须与资产声明区完全一致。

## 上一分镜站位锚点

如果 `storyboard_prompts.md` 中某个 source shot 标记：

```text
uses_previous_storyboard_reference: true
reference_purpose: placement_anchor
```

且没有跨 `scene_id`，视频提示词可以保留：

```text
参考@上一分镜_站位，保持人物空间关系、朝向和相对位置不变
```

该锚点只用于站位、朝向、空间比例和连续性，不用于复制表情、动作、服装或完整画面。

## 自检

视频提示词生成完成后必须通过：

```bash
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase video
python scripts/validate_seedance_video_prompts.py local_runs/YYYY-MM-DD/project_slug
```

检查重点：

- 每个 storyboard shot 被且仅被一个 `V###` 覆盖。
- 合并的 source shots 连续、有序、同一 `scene_id`。
- `duration_seconds` 等于 source shots 时长总和，且不超过 {max_generated_clip_seconds} 秒。
- 每条 `V###` 有 `merge_decision` 和 `frame_references`。
- Markdown 包含 `【自检通过项】`、`【资产声明区】`、`【中文视频提示词】`。
- 不输出英文 Prompt 或中英对照。
- 默认不出现 `@PROP`。
- 写入无字幕、无 Logo、无水印约束。
