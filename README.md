# 短视频创作平台

## V3.1 生产安全模型

- 所有阶段通过 `python scripts/run_pipeline.py RUN_DIR ...` 进入，未批准上游会被程序阻断。
- `outputs/drafts/` 只保存草稿；`outputs/approved/` 才能进入最终交付。
- 校验分为 `--level structure`、`--level draft`、`--level production`。只有 production 通过才可交付。
- 图片队列逐任务持久化，支持有限重试、断点续跑和 Provider 结果登记。
- 机械构建器只生成候选或草稿；视频段合并、逐镜提示词和正式视频提示词仍由对应 AI Skill 判断。
- `local_runs/` 和真实生产素材永不提交代码仓库，CI 会运行仓库策略检查。

常用命令：

```text
python scripts/run_pipeline.py RUN_DIR status
python scripts/validate_project.py RUN_DIR --level draft
python scripts/execute_image_queue.py RUN_DIR --provider codex_builtin
python scripts/resume_image_queue.py RUN_DIR
python scripts/validate_project.py RUN_DIR --level production
python scripts/package_production.py RUN_DIR --mode portable
```

这是一套面向即梦画布生产的短视频创作流程仓库。仓库不直接生成最终视频，也不管理外部生成后的成片审查；它负责把用户想法转化为剧本、风格约束、分镜序列、资产清单、资产/分镜生图提示词和最终视频提示词。

## 核心原则

- 剧本优先：`story_generation` 只优化剧本，不输出结构化 JSON。
- 用户确认：剧本与视觉方向都需要用户确认后再进入下游。
- 艺术先行：艺术总监先定画面风格、色调、光线和 AI 视觉执行要求；导演后续负责具体构图与分镜。
- 最小必要输入：下游只读取当前阶段真正需要的文件。
- 人物资产：基础资产用稳定人物名；仅在年龄、持续服装/发型、持续伤痕或身份转变时使用 `人物稳定名_变体名`。临时情绪和动作不拆资产，名称不加“状态”二字。
- 场景资产：按稳定场景名固定，普通光线、时间、天气变化不拆新场景。
- 资产提示词输入保持简单：`story.md + style_bible.md + asset_type + asset_name + output_prompt_path`。
- 分镜参考图：每个 `S###` 必须标明首帧、尾帧或关键帧，并判断是否引用上一分镜作站位参考。
- 视频提示词：可在同一 `scene_id` 内合并连续 `S###`，合并总时长必须不超过 30 秒。

## 推荐试跑顺序

1. 执行 `scripts/init_local_run.ps1 -ProjectSlug your-project-slug` 初始化本地创作目录。
2. 填写 `local_runs/YYYY-MM-DD/your-project-slug/inputs/idea_brief.md`。
3. 运行创意阶段（`idea_generation` 策略槽对应的 Skill，如 `advertising-idea-strategy`），把用户的模糊想法提炼为 `outputs/brief.md` 创意简报。
4. 用户确认创意简报后，运行 `skills/story_generation.md`，基于 `brief.md` 产出 `outputs/story.md`。
5. 用户与剧本专家反复讨论，直到用户确认剧本可以进入下一阶段。
6. 运行 `skills/art_direction.md`，用户确认后产出 `outputs/style_bible.md`。
7. 运行 `skills/storyboard_director.md`，产出 `outputs/storyboard.json`。
8. 运行 `skills/asset_executor.md`，产出 `outputs/asset_manifest.json` 和 `outputs/shot_asset_map.json`。
9. 根据 `asset_manifest.json` 里的 `output_prompt_path`，循环运行人物、场景、必要道具提示词生成器。
10. 每次提示词生成器只输入：剧本、风格圣经、资产类型、资产名和输出路径。
11. 运行或手动执行 `skills/image_generation_executor.md` 生成资产图片；每个任务只生成一张图片文件。
12. 将有效资产图片回填到 `outputs/assets/characters/`、`outputs/assets/scenes/`、`outputs/assets/props/`。
13. 运行 `skills/storyboard_prompt_generator.md`，产出 `outputs/storyboard_prompts.md`，明确每个分镜的帧角色和上一分镜站位参考判断。
14. 生成分镜参考图，并回填到 `outputs/storyboards/S001.png`、`S002.png` 等。
15. 运行 `skills/video_prompt_generator.md`，根据连续 shot、同一 scene_id 和 30 秒上限生成 `outputs/video_prompts.md` 与 `outputs/video_prompts.json`。

## 输出目录

```text
outputs/
├── story.md
├── style_bible.md
├── storyboard.json
├── asset_manifest.json
├── shot_asset_map.json
├── storyboard_prompts.md
├── video_prompts.md
├── video_prompts.json
├── assets/
│   ├── characters/
│   ├── scenes/
│   └── props/
└── storyboards/
```

## 命名规范

- 人物：基础资产用稳定人物名；必要变体用 `人物稳定名_持续变体`，例如 `林小满_雨夜居家装`，不加“状态”二字。
- 人物资产图：一个人物或持续变体生成一张 2x2 身份四宫格，包含面部近景、全身正面、全身三分之四侧面、全身背面。
- 场景：优先使用具象场景名，例如 `雨夜客厅场景`；无明确名称时用 `场景1`、`场景2`。
- 道具：只管控核心剧情道具；普通背景物件不强行生成独立资产。
- 分镜：`S{三位数序号}`，例如 `S001`。
- 场景/时空单元：`SC{三位数序号}`，例如 `SC001`。
- 视频提示词：`V{三位数序号}`，例如 `V001`，可合并多个连续分镜。

## 校验

```bash
python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase all
python scripts/validate_seedance_video_prompts.py local_runs/YYYY-MM-DD/project_slug
```

## 仓库边界

- 仓库保存流程、Skill、配置模板、schema、检查规则和文档。
- 真实创作产物、参考素材、生成图片、日志和 `checkpoint.json` 放入本地 `local_runs/YYYY-MM-DD/project_slug/`，不提交仓库。
- `story_generation` 不输出 `story.json`；镜头和资产结构化分别交给导演和资产执行官。
- `art_direction` 不负责具体构图，构图、景别、机位和镜头调度由 `storyboard_director` 处理。
