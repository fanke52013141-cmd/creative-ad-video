# Local Run Template

复制本文件内容到：

```text
local_runs/YYYY-MM-DD/project_slug/notes.md
```

## Project

- Slug:
- Date:
- Owner:
- Goal:

## Input

- Idea brief:
- References:
- Constraints:
- User visual style / references:
- User character / scene references:

## Generation Modes

- Asset image generation: `jimeng_web_manual | chatgpt_web | codex_direct | external_manual`
- Storyboard image generation: `jimeng_web_manual | chatgpt_web | codex_direct | external_manual`
- Video generation: `jimeng_canvas_manual`。

## Phase Log

| Phase | Status | Artifact | Notes |
| -- | -- | -- | -- |
| story_generation | pending | `outputs/story.md` | 只做剧本，不输出 JSON |
| art_direction | pending | `outputs/style_bible.md` | 用户有风格则继承；无风格则先给候选方案；不做具体构图 |
| storyboard_director | pending | `outputs/storyboard.json` | 负责具体构图、景别、镜头和分镜结构化 |
| asset_executor | pending | `outputs/asset_manifest.json`, `outputs/shot_asset_map.json` | 固定人物状态资产、场景资产、核心道具和 shot 映射 |
| asset_prompt_generation | pending | `outputs/assets/**.md` | 输入为 story、style、asset_type、asset_name、output_prompt_path |
| image_generation_executor | optional | `outputs/image_generation_queue.json`, `outputs/image_generation_queue.md`, `outputs/assets/**.png` | 一个资产任务只生成一张图片文件 |
| storyboard_prompt_generator | pending | `outputs/storyboard_prompts.md` | 每个 shot 写帧角色和上一分镜站位判断 |
| video_prompt_generator | pending | `outputs/video_prompts.md`, `outputs/video_prompts.json` | 合并连续 S，记录 merge_decision 和 frame_references |

## Asset Prompt Generation Steps

1. 从 `asset_manifest.json` 中选择一个 `generation_required=true` 且有 `output_prompt_path` 的资产。
2. 调用对应生成器，输入：
   - `outputs/story.md`
   - `outputs/style_bible.md`
   - `asset_type`
   - `asset_name`
   - `output_prompt_path`
3. 不传 `task_id`。
4. 不传 `asset_payload`。
5. 不额外维护 `asset_prompt_tasks.json`。

## Asset Image Generation Steps

1. 资产提示词完成后，运行或手动执行 `image_generation_executor`。
2. 选择生成方式：即梦网页端、ChatGPT 网页端、Codex 直接生成或其他外部工具。
3. 每个 `asset_image_task` 只生成一张图片文件。
4. 人物资产图允许是一张 21:9 多视角单图，包含特写、正面、侧面、后视图。
5. 场景资产图是一张稳定空间结构参考图。
6. 道具只有 `generation_required=true` 时才回填独立道具图；普通道具不需要。
7. 将有效资产图片回填到：
   - `outputs/assets/characters/`
   - `outputs/assets/scenes/`
   - `outputs/assets/props/`

## Storyboard Prompt And Image Steps

1. 按 `S###` 循环运行 `storyboard_prompt_generator`。
2. 每条分镜提示词必须写：
   - `frame_role: first_frame | last_frame | keyframe`（来自视频段计划）
   - `uses_previous_storyboard_reference: true | false`
3. 只有同一 `scene_id` 且站位关系连续时，才引用上一分镜图作为 `placement_anchor`。
4. 生成分镜参考图并回填到 `outputs/storyboards/S001.png`、`S002.png` 等。

## Video Prompt Steps

1. 全部分镜图生成完后运行 `video_prompt_generator`。
2. 输入：
   - `outputs/storyboard.json`
   - `outputs/storyboard_prompts.md`
   - `outputs/storyboards/`
   - `outputs/shot_asset_map.json`
   - `outputs/assets/`
3. 只在同一 `scene_id` 内合并连续 `S###`。
4. 合并总时长必须 `<= {max_generated_clip_seconds}s`。
5. 每条 `V###` 必须写：
   - `merge_decision`
   - `frame_references`

## Final Handoff Checklist

- [ ] `outputs/story.md`
- [ ] `outputs/video_prompts.md`
- [ ] `outputs/video_prompts.json`
- [ ] `outputs/assets/characters/` 中只保留有效角色资产
- [ ] `outputs/assets/scenes/` 中只保留有效场景资产
- [ ] `outputs/storyboards/` 中包含全部有效分镜参考图

道具资产不作为单独最终交付目录；道具信息写入 `video_prompts.md` 正文。

## Validation

初始化后运行：

```text
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase initialized
```

完整项目运行：

```text
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase all
```

## Problems Found

-

## Reusable Improvements

记录可以反哺仓库的流程问题，不记录具体私有创作内容。

-
