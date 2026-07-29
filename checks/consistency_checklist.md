# Consistency Checklist

本清单只覆盖当前 7 阶段扁平主流程：

```text
story_generation
→ art_direction
→ storyboard_director
→ asset_executor
→ asset_prompt_generation
→ storyboard_prompt_generator
→ video_prompt_generator
```

## 流程一致

- [ ] `README.md`、`config/config.yaml`、`checkpoint.template.json`、`docs/flow.md` 的阶段顺序一致。
- [ ] `scripts/validate_project.py` 的 `PIPELINE` 与 `checkpoint.template.json.phase_order` 一致。
- [ ] 当前主流程不要求 `outputs/01_story/` 到 `outputs/07_final_delivery/` 这类旧分层目录。
- [ ] 当前主流程不要求 `SHOT_001`、`CHAR_001`、`ENV_001`、`PROP_001` 这类旧 ID 作为主名称。
- [ ] 当前主流程不要求 `asset_manifest_builder`、`shot_video_prompt_generator` 或 `production_package_builder` 作为必经阶段。

## 剧本阶段

- [ ] `story_generation` 只输出 `outputs/story.md`。
- [ ] 不输出 `story.json` 或 `story_index.json`。
- [ ] 不在剧本阶段拆镜头、拆资产或写图片/视频提示词。

## 艺术方向阶段

- [ ] `art_direction` 只输出 `outputs/style_bible.md`。
- [ ] `style_bible.md` 包含 `画面风格`、`整体色调`、`光线风格`、`AI 视觉执行要求`。
- [ ] `style_bible.md` 不包含硬字段 `## 构图倾向` 或 `## 禁止出现的视觉元素`。
- [ ] 不输出 `art_direction.json` 作为主产物。

## 分镜阶段

- [ ] `storyboard_director` 输出 `outputs/storyboard.json`。
- [ ] 每个 shot 的 `shot_id` 使用 `S###`，从 `S001` 连续递增。
- [ ] 每个 shot 的 `scene_id` 使用 `SC###`。
- [ ] 每个 shot 的 `duration_seconds` 大于 0 且不超过 15。
- [ ] 每个 shot 只包含当前阶段字段：`shot_id`、`scene_id`、`duration_seconds`、`framing`、`camera_move`、`action_desc`。
- [ ] `storyboard.json` 不包含 `characters_in_shot`、`location`、`character_ids`、`prop_ids`、`asset_ids` 或 `prompt_cn`。

## 资产阶段

- [ ] `asset_executor` 输出 `outputs/asset_manifest.json` 和 `outputs/shot_asset_map.json`。
- [ ] 人物资产名使用 `人物稳定名_状态`。
- [ ] 场景资产名使用稳定具象场景名，不因普通光线、时间、天气变化拆分。
- [ ] 道具只保留核心剧情道具；普通背景物件不强行生成独立资产。
- [ ] 资产主名称不使用 `CHAR_001`、`ENV_001`、`PROP_001` 或 `AUDIO_001`。
- [ ] `generation_required` 使用 boolean，不使用字符串。
- [ ] `generation_required=true` 的资产必须有单个 `output_prompt_path`。
- [ ] 不使用旧字段 `prompt_outputs`、`task_id`、`asset_payload` 或 `asset_prompt_tasks.json`。
- [ ] `shot_asset_map.json` 对每个 `S###` 有且仅有一条映射。
- [ ] `shot_asset_map.json` 中引用的资产名都存在于 `asset_manifest.json`。

## 资产提示词阶段

- [ ] 人物、场景、道具提示词生成器每次只处理一个资产。
- [ ] 输入只包含 `story.md`、`style_bible.md`、`asset_type`、`asset_name`、`output_prompt_path`。
- [ ] 每个 `generation_required=true` 的资产提示词文件已生成到对应路径。
- [ ] 人物资产图可以是一张 21:9 多视角单图，但仍只算一个资产输出。

## 分镜提示词阶段

- [ ] `storyboard_prompt_generator` 输出 `outputs/storyboard_prompts.md`。
- [ ] 每个 `S###` 都有对应分镜图提示词段落。
- [ ] 每个 `S###` 都写明 `recommended_frame_role: first_frame | last_frame | keyframe`。
- [ ] 每个 `S###` 都写明 `uses_previous_storyboard_reference: true | false`。
- [ ] 第一条分镜不引用上一分镜。
- [ ] 引用上一分镜时，`source_shot_id` 必须是当前 shot 的前一条 shot。
- [ ] 不跨 `scene_id` 引用上一分镜。
- [ ] 引用上一分镜只用于站位、朝向、空间比例和连续性，不复制完整画面。

## 分镜图片阶段

- [ ] 分镜参考图按 `outputs/storyboards/S001.png`、`S002.png` 等路径回填。
- [ ] 分镜参考图只作为后续视频提示词的首帧、尾帧或关键帧参考。
- [ ] 生成图片、参考素材和真实项目产物不提交仓库。

## 视频提示词阶段

- [ ] `video_prompt_generator` 输出 `outputs/video_prompts.md` 和 `outputs/video_prompts.json`。
- [ ] 每个 `V###` 的 `task_type` 是 `pipeline_shot_generation`。
- [ ] 每个 `V###` 的 `source_shots` 是非空、连续、有序的 `S###` 列表。
- [ ] 每个 `V###` 的所有 `source_shots` 属于同一 `scene_id`。
- [ ] 每个 `V###` 的 `duration_seconds` 等于其 `source_shots` 时长总和。
- [ ] 每个 `V###` 的总时长不超过 {max_generated_clip_seconds} 秒。
- [ ] 合并多个 shot 时，`merge_decision.strategy` 使用 `merged_*`。
- [ ] 单个 shot 不使用 `merged_*` 策略。
- [ ] 每个 `V###` 的 `frame_references` 覆盖且只覆盖当前 `source_shots`。
- [ ] 所有 storyboard shots 被且仅被一个 `V###` 覆盖。
- [ ] `video_prompts.md` 包含 `【自检通过项】`、`【资产声明区】`、`【中文视频提示词】`。
- [ ] 视频提示词不包含 `English Prompt`、`中英对照` 或 `@PROP`。
- [ ] 视频提示词包含无字幕、无 Logo、无水印约束。

## 校验与 CI

- [ ] `python scripts/validate_project.py examples/minimal_run --phase all` 通过。
- [ ] `python scripts/validate_seedance_video_prompts.py examples/minimal_run` 通过。
- [ ] GitHub Actions 同时编译 `validate_project.py` 和 `validate_seedance_video_prompts.py`。
- [ ] 新增或修改 schema 后，CI 能解析全部 `schemas/*.json`。

## 仓库边界

- [ ] 不提交 `local_runs/`、`creative_runs/`、`runs/`。
- [ ] 不提交真实参考图片、视频、音频、生成图、生成视频、剪辑工程。
- [ ] 不提交 `.env`、API key、cookie、token、本地账号信息。
- [ ] 示例项目必须小体量、脱敏、可复现。
