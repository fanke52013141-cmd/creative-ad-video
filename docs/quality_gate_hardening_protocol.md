# Quality Gate Hardening Protocol

本协议用于防止“文件存在但内容不可生产”的假通过问题。

## 核心原则

1. 下游不得只凭 Markdown 判断阶段通过，必须读取 JSON 和 schema。
2. 生成提示词阶段不得声明不存在、未生成、未批准或需要重生的参考图。
3. 当前主流程只校验 7 阶段扁平产物；外部生成、审查和最终打包属于后续扩展流程，不应伪装成已完成主流程。
4. `completed` 不是文件齐全，而是当前阶段关键质量门全部通过。

## 当前主流程必须硬阻断的情况

### 剧本阶段

- 生成 `story.json` 或 `story_index.json`。
- `story.md` 缺失。

### 艺术方向阶段

- `style_bible.md` 缺少 `画面风格`、`整体色调`、`光线风格` 或 `AI 视觉执行要求`。
- `style_bible.md` 出现 `## 构图倾向` 或 `## 禁止出现的视觉元素` 这类硬字段。
- 输出 `art_direction.json` 作为主产物。

### 分镜阶段

- `storyboard.json` 缺失或不是对象。
- `shots` 为空。
- `shot_id` 不是从 `S001` 开始连续递增。
- `scene_id` 不符合 `SC###`。
- `duration_seconds <= 0` 或 `> 15`。
- 在 `storyboard.json` 中出现后置阶段字段，例如 `characters_in_shot`、`location`、`character_ids`、`prop_ids`、`asset_ids`、`prompt_cn`。

### 资产阶段

- `asset_manifest.json` 或 `shot_asset_map.json` 缺失。
- 资产主名称使用 `CHAR_001`、`ENV_001`、`PROP_001`、`AUDIO_001` 这类抽象 ID。
- 资产项使用旧字段 `prompt_outputs`。
- `generation_required=true` 但缺少 `output_prompt_path`。
- `shot_asset_map.json` 没有且仅有一次覆盖每个 `S###`。
- `shot_asset_map.json` 引用了资产清单不存在的资产名。

### 资产提示词阶段

- 任一 `generation_required=true` 的资产提示词文件不存在。
- 提示词生成器输入退回旧队列式字段，例如 `task_id`、`asset_payload`、`prompt_outputs`。

### 分镜提示词阶段

- `storyboard_prompts.md` 缺失。
- 任一 `S###` 缺少提示词段落。
- 任一 `S###` 缺少来自视频段计划的 `frame_role`，或值不是 `first_frame | last_frame | keyframe`。
- 任一 `S###` 缺少 `uses_previous_storyboard_reference: true | false`。
- 第一条分镜引用上一分镜。
- 跨 `scene_id` 引用上一分镜。
- 引用上一分镜但没有限定为站位/空间比例/连续性锚点。

### 视频提示词阶段

- `video_prompts.md` 或 `video_prompts.json` 缺失。
- `video_prompts.md` 缺少 `【自检通过项】`、`【资产声明区】` 或 `【中文视频提示词】`。
- `video_prompts.md` 出现 `English Prompt`、`中英对照` 或 `@PROP`。
- `video_prompts.md` 缺少无字幕、无 Logo、无水印约束。
- `video_prompts.json` 没有覆盖每个分镜，或某个分镜被覆盖多次。
- `source_shots` 为空、重复、乱序、不连续或引用未知分镜。
- `scene_id` 与所有 `source_shots` 不一致。
- 合并总时长超过 {max_generated_clip_seconds} 秒。
- `duration_seconds` 不等于 `source_shots` 的时长总和。
- 合并多个 shot 但 `merge_decision.strategy` 不是 `merged_*`。
- 单个 shot 却使用 `merged_*`。
- `frame_references` 没有且仅覆盖当前 `source_shots`。

## 推荐校验命令

```bash
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase initialized
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase story
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase art
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase storyboard
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase assets
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase asset_prompt_generation
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase storyboard_prompt_generation
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase video
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase all
```

专项视频提示词表层检查：

```bash
python scripts/validate_seedance_video_prompts.py local_runs/YYYY-MM-DD/project_slug
```

## 暂不支持的命令

当前主校验器不提供 `--phase final`。如果后续恢复外部生成审查和最终打包阶段，必须先在 `scripts/validate_project.py` 中新增对应 validator，再把 `final` 加入命令文档。
