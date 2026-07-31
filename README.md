# 短视频创作平台

## V3.1 生产安全模型

这是一套面向即梦画布生产的广告短视频创作流程仓库。仓库不直接管理外部生成后的最终成片，而是负责把用户想法转化为创意简报、剧本、风格约束、分镜序列、资产、视频段计划、分镜参考图和最终视频提示词。

### 流程真值来源

当文档、Schema 与 Skill 描述出现冲突时，按以下优先级判断：

1. `scripts/pipeline_runtime.py` 中的 `STAGES`：受门禁保护的正式阶段顺序。
2. 当前阶段 Skill 的 Inputs / Outputs / Quality Gate：阶段契约。
3. `scripts/stage_gate.py` 与 `scripts/validate_project.py`：产物和校验要求。
4. README、流程图及其他说明文档。

说明文档不得改变状态机顺序。发现不一致时，应先修正文档或校验契约，不得凭说明文档跳过正式阶段。

## 核心原则

- 所有受控阶段通过 `python scripts/run_pipeline.py RUN_DIR ...` 进入，未完成或未批准的上游会阻断下游。
- `outputs/drafts/` 只保存草稿；`outputs/approved/` 才能进入最终交付。
- 校验分为 `--level structure`、`--level draft`、`--level production`；只有 production 通过才可交付。
- 剧本优先：`story_generation` 只优化剧本，不输出 `story.json`。
- 用户确认：剧本与艺术方向必须确认后才能进入下游。
- 艺术先行：艺术总监定义风格、色调、光线和 AI 视觉执行规则；导演负责具体构图、景别、机位和镜头调度。
- 资产单一来源：人物、场景和关键道具由 `asset_manifest.json` 统一登记。
- 分镜先分组：资产审核通过后，必须先生成 `video_segment_plan.json`，再生成分镜提示词。
- 帧角色不可猜测：每个 `S###` 的 `first_frame`、`last_frame` 或 `keyframe` 必须从已批准的视频段计划读取。
- 自动生图可选，正式图片产物不可缺失：可以使用自动 Provider，也可以外部手动生成并登记；但继续进入依赖图片的阶段前，必须存在已批准的资产图和分镜图。
- 视频段可在同一 `scene_id` 内合并连续 `S###`，总时长不得超过当前垂类配置的 `max_generated_clip_seconds`。
- `local_runs/`、真实生产素材、日志和 checkpoint 不提交仓库。

## 正式阶段顺序

`pipeline_runtime.py` 当前定义的受控阶段如下：

```text
story_generation
→ art_direction
→ storyboard_director
→ storyboard_sequence_review
→ asset_executor
→ asset_prompt_generation
→ asset_image_generation
→ generated_asset_review
→ video_segment_planning
→ storyboard_prompt_generation
→ storyboard_image_generation
→ storyboard_visual_review
→ video_prompt_generation
→ final_package
```

其中最容易混淆的一段是：

```text
资产审核
→ 视频段规划
→ 分镜提示词
→ 分镜图片
→ 分镜视觉审核
→ 视频提示词
```

`storyboard_prompt_generator` 必须读取 `video_segment_plan.json`，因此不得先生成正式分镜提示词、再反向决定镜头组。

## 推荐试跑顺序

1. 执行 `scripts/init_local_run.ps1 -ProjectSlug your-project-slug` 初始化本地目录。
2. 填写 `local_runs/YYYY-MM-DD/your-project-slug/inputs/idea_brief.md`。
3. 运行广告创意 Skill，产出 `outputs/brief.md`。创意阶段目前属于正式状态机之前的前置步骤。
4. 用户确认创意简报后，进入 `story_generation`，产出并确认 `outputs/story.md`。
5. 进入 `art_direction`，产出并确认 `outputs/style_bible.md`。
6. 进入 `storyboard_director`，产出 `outputs/storyboard.json`。
7. 运行 `storyboard_sequence_review`，检查时长、叙事顺序、场景切换和广告信息节奏。
8. 运行 `asset_executor`，产出 `outputs/asset_manifest.json` 和 `outputs/shot_asset_map.json`。
9. 根据 `asset_manifest.json` 的 `output_prompt_path` 生成人物、场景和必要道具提示词。
10. 自动或手动生成资产图片，并把有效结果登记到对应资产目录。
11. 运行 `generated_asset_review`，批准角色、场景、产品和关键道具的正式参考图。
12. 运行 `video_segment_planner`，产出 `outputs/video_segment_plan.json`：将连续、同场景且真正具备动作或空间连续性的分镜合并为 `V###`，同时为每个 `S###` 指定帧角色。
13. 按 `shot_id` 循环运行 `storyboard_prompt_generator`。每次读取视频段计划中的 `frame_role`，并判断是否引用上一分镜作为站位锚点。
14. 生成分镜参考图并回填到 `outputs/storyboards/S001.png`、`S002.png` 等。
15. 运行 `storyboard_visual_review`，检查人物身份、资产一致性、站位延续、产品包装和构图可执行性。
16. 按 `V###` 循环运行 `video_prompt_generator`，生成正式视频提示词与 manifest。
17. 运行最终校验并生成 `final_package_manifest.json`。

## 视频段与分镜板

视频段计划示例：

```text
V001
├── S001  first_frame
├── S002  keyframe
└── S003  last_frame
```

正式分镜图片仍按镜头保存：

```text
outputs/storyboards/S001.png
outputs/storyboards/S002.png
outputs/storyboards/S003.png
```

这些图片共同构成 V001 的生成控制帧。可以额外制作 `V001_storyboard_board.png` 作为人工审核联系表，但联系表不是 `video_segment_plan.json` 和逐镜图片的替代品。

## 常用命令

```text
python scripts/run_pipeline.py RUN_DIR status
python scripts/run_pipeline.py RUN_DIR start --stage video_segment_planning
python scripts/run_pipeline.py RUN_DIR complete --stage video_segment_planning
python scripts/validate_project.py RUN_DIR --level draft
python scripts/execute_image_queue.py RUN_DIR --provider codex_builtin
python scripts/resume_image_queue.py RUN_DIR
python scripts/validate_project.py RUN_DIR --level production
python scripts/package_production.py RUN_DIR --mode portable
```

## 输出目录

```text
outputs/
├── story.md
├── style_bible.md
├── storyboard.json
├── asset_manifest.json
├── shot_asset_map.json
├── image_generation_queue.json
├── video_segment_plan.json
├── reviews/
│   ├── storyboard_sequence_review.json
│   ├── generated_asset_review*.json
│   └── storyboard_visual_review.json
├── assets/
│   ├── characters/
│   ├── scenes/
│   └── props/
├── approved/
│   ├── storyboard_prompts/
│   ├── storyboards/
│   └── video_generation/
├── storyboards/
└── final_package_manifest.json
```

## 命名规范

- 人物：基础资产使用稳定人物名；只有年龄、持续服装/发型、持续伤痕或身份转变时才使用 `人物稳定名_持续变体`，不加“状态”二字。
- 人物资产图：一个人物或持续变体生成一张 21:9 身份设定图，包含面部近景、正面、侧面和背面。
- 场景：按稳定空间命名；普通光线、时间或天气变化不拆成新场景。
- 道具：只管控反复出现且影响剧情的关键道具；普通背景物件在分镜正文中描述。
- 分镜：`S{三位数序号}`，例如 `S001`。
- 场景/时空单元：`SC{三位数序号}`，例如 `SC001`。
- 视频段：`V{三位数序号}`，例如 `V001`，可覆盖多个连续分镜。

## 校验

```bash
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase all
python scripts/validate_seedance_video_prompts.py local_runs/YYYY-MM-DD/project_slug
```

生产校验必须确认：

- 每个 storyboard shot 被且仅被一个视频段覆盖。
- 视频段内 source shots 连续、同一 `scene_id`，且时长不超过垂类配置。
- 每个分镜提示词的 `frame_role` 与视频段计划一致。
- 需要上一分镜站位参考时，只继承相对位置、朝向、空间比例和连续性。
- 资产图、分镜图及其审核结果均为最新批准版本。

## 仓库边界

- 仓库保存流程、Skill、配置模板、Schema、检查规则和文档。
- 真实创作产物、参考素材、生成图片、日志和 `checkpoint.json` 放入本地 `local_runs/YYYY-MM-DD/project_slug/`。
- `story_generation` 不输出 `story.json`；镜头和资产结构化分别交给导演和资产执行官。
- `art_direction` 不负责具体构图。
- `video_segment_planner` 只决定分组和帧角色，不写图片或视频提示词。
- `storyboard_prompt_generator` 不重新分组，也不得自行推断帧角色。
- `video_prompt_generator` 必须遵守已批准的视频段计划，不得重新合并或拆分。