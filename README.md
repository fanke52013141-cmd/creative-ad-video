# AI 广告视频前期生产流水线

## V8.0：分镜板优先的视频生成契约

本仓库把广告需求转换为创意简报、剧本、视觉方向、分镜、资产计划、图片提示词、媒体版本、分镜板和视频提示词。实际视频生成、剪辑与投放仍属于外部执行范围。

V8 保留 V7 的不可变 Artifact/Approval 机制，并增加：

- `config/pipeline.yaml` 是阶段、DAG、executor、审批、skip 和声明产物的唯一事实源。
- 上游计划 Manifest 完成后不可修改；媒体结果写入独立 Media Manifest。
- 每个普通文件和媒体文件都登记为 Artifact Revision。
- Approval Registry 只审批真实 Artifact Revision，并绑定 SHA-256。
- 资产和分镜板媒体批准后被替换，会阻止 Production、打包和 Delivery。
- 所有正式 Codex Skill 位于 `.agents/skills/<name>/SKILL.md`。
- 视频提示词只使用 `video_prompt_manifest.json`，不再支持 `video_prompts.json`。
- 每个 `V###` 视频生成单元必须为 4–30 秒；短镜头只能在同场景内合并，禁止虚构填充时长。
- 未特别指定画幅时使用 `16:9`，并贯穿分镜包、视频提示词和最终生产包。
- 视频模型只引用分镜板、人物和 `advertised_product` 商品，不再接收场景、装饰、特效或普通道具参考。
- 广告文字必须在 `storyboard.json` 声明、直接生成到分镜板并逐字审批，禁止后期补字回退。

## 安装与初始化

```text
python -m pip install -r requirements.txt
powershell -File scripts/init_local_run.ps1 -ProjectSlug your-project-slug
python scripts/pipeline_engine.py RUN_DIR ready
python scripts/pipeline_engine.py RUN_DIR run --stage idea_generation
```

Checkpoint 的阶段结构由 PipelineSpec 动态生成，不在模板中复制阶段列表。

### 项目产物与框架仓库隔离（推荐）

本仓库只存放标准化的生产流程。**实际客户项目的产物（brief、storyboard、媒体、审批记录等）不要提交回这个仓库**。

推荐把每个 run 建在框架仓库**之外**，让产物物理上不在 git 仓库内，从源头杜绝误提交：

```text
# 在仓库外指定 run 根目录（例如 D:\client-projects）
powershell -File scripts/init_local_run.ps1 -ProjectSlug your-project-slug -RunRoot D:\client-projects

# 之后所有命令都传外部 run 的绝对路径
python scripts/pipeline_engine.py D:/client-projects/2026-08-05/your-project-slug ready
python scripts/validate_project.py D:/client-projects/2026-08-05/your-project-slug --level draft
```

要点：
- `-RunRoot` 缺省时仍建在仓库内 `local_runs/`（向后兼容），但那样**产物就在 git 仓库工作区内**，有被 `git add` 误提交的风险。
- `local_runs/` 已被 `.gitignore` 忽略，但 `.gitignore` 只对**未跟踪**文件生效；一旦某次 `git add local_runs/` 过，之后所有改动都会被跟踪。所以最稳妥的做法是让 run 完全在仓库外。
- 框架仓库的 `main` 只应包含框架代码，任何真实项目数据都不应出现。

## DAG 执行与审批

`pipeline_engine.py` 为每个 ready stage 创建 `outputs/tasks/<stage>/TASK-*.json`。任务包含 Skill 名称、真实 Skill 路径、输入 Artifact Revision 和声明输出。完成阶段：

```text
python scripts/run_pipeline.py RUN_DIR complete --stage STAGE
```

三个策略阶段需要人工批准：

```text
python scripts/run_pipeline.py RUN_DIR approve --stage idea_generation --actor USER --reason "创意通过"
python scripts/run_pipeline.py RUN_DIR approve --stage art_direction --actor USER --reason "视觉通过"
python scripts/run_pipeline.py RUN_DIR approve --stage storyboard_director --actor USER --reason "分镜通过"
```

### 方案自动审查（idea_generation 审批前）

`idea_generation` 产出 `outputs/brief.md` 与 `outputs/story.md` 后、人工审批前，建议运行 `advertising-idea-review` 做自动创意审查：

```text
# 审查：读 brief.md + story.md → 对话中输出八维诊断报告 → 写 outputs/idea_review_feedback.md
# 由执行环境按 .agents/skills/advertising-idea-review/SKILL.md 调用
```

审查只出意见、不放行；放行永远由人工 `approve` / `reject` 决定。`reject` 后进入修订轮：`advertising-idea-strategy` 会自动读取 `outputs/idea_review_feedback.md` 逐条修订，修订后**不自动二次审查**，除非人工明确要求。反馈文件是流程状态，不进 Artifact/Approval Registry、不参与交付校验。

## 资产提示词与媒体

资产提示词完成后建立哈希清单：

```text
python scripts/build_asset_prompt_manifest.py RUN_DIR
python scripts/build_image_queue.py RUN_DIR
python scripts/execute_image_queue.py RUN_DIR --provider codex_builtin
python scripts/register_image_result.py RUN_DIR IMG-0001 --source-file GENERATED_FILE
python scripts/approve_media.py RUN_DIR asset ASSET_ID --actor USER
```

资产计划保存在 `asset_manifest.json`，图片结果只写入 `asset_media_manifest.json`。

## 分镜板与视频提示词

```text
python scripts/build_storyboard_packets.py RUN_DIR
python scripts/register_storyboard_result.py RUN_DIR SB001 GENERATED_FILE
python scripts/approve_media.py RUN_DIR board SB001 --actor USER --confirm-no-extra-text
# 含广告文字时，每条文字按分镜顺序重复传入：
python scripts/approve_media.py RUN_DIR board SB002 --actor USER --verified-text "现在下单" --confirm-no-extra-text
python scripts/build_video_prompt_manifest.py RUN_DIR
```

关系规则：

- 每个 `S###` 恰好属于一个 `SB###`。
- 每个 `SB###` 只属于一个 `V###`，每板最多四镜。
- 每个 `V###` 为 4–30 秒；`SB###` 只是关键帧载体，不单独承担 4 秒下限。
- 分镜板计划与图片结果分别保存在 `storyboard_board_manifest.json` 和 `storyboard_media_manifest.json`。
- 视频参考白名单是分镜板、人物和广告商品；场景只服务于分镜板生成。
- 默认画幅是 `16:9`。
- 不允许通过目录顺序或第一个 glob 结果猜测关系。

自动图片 executor 可以按 PipelineSpec 跳过，但只允许 Draft 继续；Production 仍要求媒体存在且已批准。

## 校验层级

```text
python scripts/validate_project.py RUN_DIR --level structure
python scripts/validate_project.py RUN_DIR --level draft
python scripts/validate_project.py RUN_DIR --level production
python scripts/validate_project.py RUN_DIR --level delivery
```

| Level | 要求 |
|---|---|
| structure | 剧本、风格、分镜、资产和视频段结构正确 |
| draft | 提示词及 V/SB/S Manifest 完整；允许草稿级媒体 skip |
| production | 所有必需媒体均有有效 Artifact Revision 和哈希审批 |
| delivery | 最终包完成，包内文件大小和 SHA-256 全部匹配 |

只有 `--level delivery` 授权最终交付。`--phase all` 已弃用并故意失败。

## 最终打包

```text
python scripts/package_production.py RUN_DIR --mode portable
python scripts/validate_project.py RUN_DIR --level delivery
```

打包器只读取显式计划、媒体和视频 Manifest，并在每次运行时写入新的 `outputs/final_packages/PKG-*/`。

## 关键输出

```text
outputs/
├── brief.md
├── story.md
├── style_bible.md
├── storyboard.json
├── asset_manifest.json
├── shot_asset_map.json
├── asset_prompt_manifest.json
├── asset_media_manifest.json
├── video_segment_plan.json
├── storyboard_board_inputs/
├── storyboard_board_manifest.json
├── storyboard_media_manifest.json
├── video_prompts/V###.md
├── video_prompt_manifest.json
├── artifact_registry.json
├── approval_registry.json
├── versions/
├── tasks/
├── final_packages/PKG-*/
└── final_package_manifest.json
```

## 旧 Run 迁移（已退役）

V6/V7 迁移脚本（`migrate_run_v6_to_v7.py`、`migrate_run_v7_to_v8.py`）已移除。当前流水线为 V8，不再支持从 V6/V7 迁入。历史迁移说明见 git 历史。

## 仓库验证

```text
python scripts/validate_pipeline_contract.py
python -m unittest discover -s tests -v
python scripts/validate_project.py examples/minimal_run --level draft
python scripts/check_document_references.py
python scripts/check_repository_policy.py
```
