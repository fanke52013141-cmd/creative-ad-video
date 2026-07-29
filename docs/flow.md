# Workflow

路径约定：真实创作在 `local_runs/YYYY-MM-DD/project_slug/` 中执行。下文的 `RUN` 代表这个 active run 目录。

## 1. Story

- Skill: `story_generation`
- Input: `RUN/inputs/idea_brief.md`
- Output: `RUN/outputs/story.md`
- Contract: 只优化剧本；不输出 `story.json`；不拆镜头、资产或提示词。

## 2. Art Direction

- Skill: `art_direction`
- Input: 用户已确认锁定的 `RUN/outputs/story.md`
- Output: `RUN/outputs/style_bible.md`
- Contract: 只定义画面风格、整体色调、光线风格和 AI 视觉执行要求；不做具体构图。

## 3. Storyboard Director

- Skill: `storyboard_director`
- Input:
  - `RUN/outputs/story.md`
  - `RUN/outputs/style_bible.md`
- Output: `RUN/outputs/storyboard.json`
- Shot fields:
  - `shot_id`
  - `scene_id`
  - `duration_seconds`
  - `framing`
  - `camera_move`
  - `action_desc`

## 4. Asset Executor

- Skill: `asset_executor`
- Input:
  - `RUN/outputs/story.md`
  - `RUN/outputs/storyboard.json`
  - 可选用户参考素材
- Output:
  - `RUN/outputs/asset_manifest.json`
  - `RUN/outputs/shot_asset_map.json`
- Contract:
  - 人物资产使用稳定人物名；仅对持续可见变化使用 `人物稳定名_持续变体`，且不加“状态”二字。
  - 不默认拆成 `人脸大头特写` 和 `全身妆造` 两个资产。
  - 场景资产按稳定场景名固定；普通光线、时间、天气变化不拆场景。
  - 普通道具正文控制；只有核心复杂道具才独立生成。
  - 每个需要生成提示词的资产只有一个 `output_prompt_path`。

## 5. Asset Prompt Generation

三路可并行执行。每次只处理一个资产。

```json
{
  "story_markdown_path": "./outputs/story.md",
  "style_bible_path": "./outputs/style_bible.md",
  "asset_type": "character | scene | prop",
  "asset_name": "资产执行官固定的资产名",
  "output_prompt_path": "本次要写出的提示词文件"
}
```

### Character

- `asset_name` 示例：`林小满_雨夜居家装`
- 输出：一份 21:9 人物状态资产图提示词。
- 同一张图中可包含人物特写、正面、侧面、后视图。

### Scene

- `asset_name` 示例：`雨夜客厅场景`
- 输出：一份单场景参考图提示词。

### Prop

- 只处理 `generation_required=true` 且确实需要独立生成的核心道具。

## 5.5 Asset Image Generation

- Skill: `image_generation_executor`
- Minimal input:
  ```json
  {
    "asset_type": "character | scene | prop",
    "asset_name": "资产名",
    "prompt_path": "资产提示词路径",
    "generation_mode": "jimeng_web_manual | chatgpt_web | codex_direct | external_manual",
    "output_image_path": "生成后的图片路径"
  }
  ```
- Output: 一张资产图片文件。
- 人物资产图允许是一张 21:9 多视角资产图；仍然只算一张图片文件。

## 6. Storyboard Prompt Generation

- Skill: `storyboard_prompt_generator`
- 按 shot 循环执行。
- Input:
  ```json
  {
    "storyboard_json_path": "./outputs/storyboard.json",
    "style_bible_path": "./outputs/style_bible.md",
    "shot_asset_map_path": "./outputs/shot_asset_map.json",
    "asset_image_root": "./outputs/assets",
    "storyboard_image_root": "./outputs/storyboards",
    "shot_id": "S001",
    "output_prompt_path": "./outputs/storyboard_prompts/S001.md"
  }
  ```
- Output: 当前 `S###` 的分镜参考图提示词，也可汇总为 `RUN/outputs/storyboard_prompts.md`。
- 必须输出：
  - `frame_role: first_frame | last_frame | keyframe`，必须来自 `video_segment_plan.json`
  - `uses_previous_storyboard_reference: true | false`
  - 如引用上一分镜，必须限定为 `placement_anchor`，只继承站位、朝向、空间比例和连续性。

## 6.5 Storyboard Image Generation

- Input:
  ```json
  {
    "shot_id": "S001",
    "prompt_path": "./outputs/storyboard_prompts/S001.md",
    "generation_mode": "chatgpt_web",
    "output_image_path": "./outputs/storyboards/S001.png"
  }
  ```
- Output: 一张分镜参考图。

## 7. Video Prompt Generation

- Skill: `video_prompt_generator`
- 在全部分镜图生成完成后运行。
- Minimal input:
  ```json
  {
    "storyboard_json_path": "./outputs/storyboard.json",
    "storyboard_prompts_path": "./outputs/storyboard_prompts.md",
    "storyboard_reference_dir": "./outputs/storyboards",
    "shot_asset_map_path": "./outputs/shot_asset_map.json",
    "asset_reference_dir": "./outputs/assets"
  }
  ```
- Output:
  - `RUN/outputs/video_prompts.md`
  - `RUN/outputs/video_prompts.json`

### Merge rule

- 合并对象是连续 `S###`，不是 `SC###`。
- 同一 `scene_id` 内的连续 shot 才允许合并。
- 合并总时长必须 `<= {max_generated_clip_seconds}s`。
- 强连续动作、同一站位关系、同一道具交互优先合并。
- 跨场景、时间跳跃、动作不连续或超过 {max_generated_clip_seconds} 秒必须拆分。

### Frame role rule

- 合并多个 shot 时，第一个 source shot 的分镜图是 `first_frame`。
- 最后一个 source shot 的分镜图是 `last_frame`。
- 中间 source shots 的分镜图是 `keyframe`。
- 每条 `V###` 必须在 `video_prompts.json` 写入 `frame_references` 和 `merge_decision`。

## Final Canvas Handoff

| 交付物 | 内容 |
|---|---|
| `outputs/story.md` | 完整剧本 |
| `outputs/video_prompts.md` | 完整视频提示词 |
| `outputs/video_prompts.json` | 结构化视频计划 |
| `outputs/assets/characters/` | 有效人物状态资产图 |
| `outputs/assets/scenes/` | 有效场景资产图 |
| `outputs/storyboards/` | 全部分镜参考图 |

道具资产不作为单独最终交付目录；普通道具写入视频提示词正文描述。
