# Changelog

## 2026-08-07 - v8.6

### Changed
- [docs] 删除 5 个零引用孤岛文档：`docs/audio_reference_protocol.md`（无音频 stage）、`docs/portable_skill_spec.md`、`docs/asset_reference_rules.md`、`docs/character_three_view_protocol.md`、`docs/video_prompt_loop_protocol.md`。
- [docs] 合并 `docs/quality_gate_matrix.md`（P0/P1 阻塞等级表）和 `docs/phase_state_machine.md`（状态机表）进 `docs/flow.md`，删除原文件。
- [docs] 删除 `docs/storyboard_loop_protocol.md`（标题与文件名不一致、残留 V6 废弃路径、内容与 SKILL 重叠）。
- [docs] `docs/iteration_protocol.md` 阶段列表改为指向 `config/pipeline.yaml`，不再重复维护 11 阶段清单；更新状态机引用从 `phase_state_machine.md` 改为 `flow.md`。

### Reason
- 5 个文档零外部引用，内容已被 SKILL 或流程文档吸收；quality_gate_matrix 与 phase_state_machine 内容独有但薄，并入 flow.md 后消除多份维护；storyboard_loop_protocol 带历史包袱且标题不一致；iteration_protocol 的阶段列表与 config/pipeline.yaml 三处重复维护。

### Compatibility
- 纯文档清理，不改变脚本、schema、阶段结构或审批动作。

## 2026-08-07 - v8.5

### Changed
- [refactor] 抽取 `scripts/manifest_io.py` 公共 helper（`read_json`/`write_json`/`resolve_aspect_ratio`），消除三个 `build_*` 脚本中逐字重复的 JSON 读写和画幅解析代码。
- [refactor] 合并 `scripts/import_generated_media.py` 与 `scripts/register_storyboard_result.py` 为统一的 `scripts/register_media_result.py --kind asset|storyboard`，消除两个导入器 8 步逐行同构的重复代码。
- [skill] 同步更新 `fulfill-image-generation/SKILL.md` 和 `execute_storyboard_image_queue.py` 的登记命令引用。
- [tests] 更新 3 处测试引用至新统一入口。

### Reason
- 三个 build 脚本各自内联了相同的 JSON 读写和画幅解析；两个媒体导入器 8 步逻辑逐行同构，仅 id 字段名/路径/stage 可参数化。合并后消除真实重复，不改变运行时行为。

### Compatibility
- 不改变 manifest 文件格式、schema、阶段结构或审批动作。
- `register_image_result.py` 保留为队列调度层，内部改为调用 `register_media_result.py --kind asset`。
- schema 合并不做：合并两个 media manifest schema 需改 manifest 文件格式+十几处引用，省的只是一个 20 行 schema 文件，投入产出比不成立。

## 2026-08-07 - v8.4

### Changed
- [repo] 退役 V6/V7 迁移链路：删除 `scripts/migrate_run_v6_to_v7.py`、`scripts/migrate_run_v7_to_v8.py`、`docs/migrations/v6-to-v7.md`、`docs/migrations/v7-to-v8.md` 及 `docs/migrations/` 目录；删除 `tests/test_pipeline_hardening.py` 中两个迁移测试用例；`README.md` 的"旧 Run 迁移"改为"已退役"说明；`CHANGELOG.md` 历史条目中的迁移脚本引用加"已废弃"注记。

### Reason
- 用户确认不再支持 V6/V7 老版本用户迁入；仓库内 example/template 已全部 V8，迁移脚本仅服务历史遗留 run，属纯历史包袱。

### Compatibility
- 不影响 V8 流水线；测试从 23 降至 21（迁移用例已删）。

## 2026-08-07 - v8.3

### Changed
- [docs] 修正三处文档里已被 `--level` 取代的旧 `--phase` 校验命令,统一为推荐的 `--level structure|draft|production|delivery`:`docs/quality_gate_hardening_protocol.md`(8 条逐 phase 命令)、`docs/repository_policy.md`、`docs/storyboard_loop_protocol.md`。
- [skill] 修复 `fulfill-image-generation/SKILL.md` 资产图循环的断链:补上前置步骤 `python scripts/build_image_queue.py RUN_DIR`,使"建队列 → 逐个执行"完整衔接,不再直接 execute 一个可能尚未生成的队列。
- [docs] 消除 `docs/flow.md` 与 `PIPELINE_FLOW.md` 的重复:创意审查回环、V8 视频生成规则、画幅默认值等统一由 `PIPELINE_FLOW.md` 维护,`docs/flow.md` 只保留阶段-产物-Gate 契约表并指向前者,去除双份派生文档。
- [docs] 为 `CHANGELOG.md` 历史条目中已失效的引用(`--phase all`、已删除的 `validate_seedance_video_prompts.py`)加 HTML 注释标注"已废弃",保留历史原貌的同时避免被当作可执行示例复制。

### Reason
- `--phase` 逐子命令虽仍可运行,但与 README/AGENTS 定的唯一推荐接口 `--level` 不一致,易误导;`fulfill-image-generation` 资产循环缺 `build_image_queue.py` 前置,存在"队列从未生成"的执行断链;`docs/flow.md` 与 `PIPELINE_FLOW.md` 内容高度重叠,属典型冗余文档,双份维护易失步。

### Compatibility
- 纯文档与说明修正,不改变脚本行为、阶段结构、schema 与审批;旧 Run 无需迁移。

## 2026-08-07 - v8.2

### Changed
- [skill] 重写 `.agents/skills/fulfill-image-generation/SKILL.md`：新增"单任务生成协议（强制）"，把资产图和分镜板图都固化为"队列逐个取任务 → 一任务一张图 → 立即登记 → 再取下一个"的循环，并新增"硬规则：禁止合并生成"与"允许的板内/图内多画面"说明，明确区分正常的板内拼接（≤4 分镜）、角色转面多视角与违规的跨板/跨资产合并。
- [script] 新增 `scripts/execute_storyboard_image_queue.py`：为分镜板补上与资产图对称的单任务分发器，一次只返回一个未完成的 `SB###` 板及其 `prompt_path`，从源头杜绝执行方一次性面对整份 `storyboard_board_manifest.json` 而批量合图。
- [script] `scripts/execute_image_queue.py` 的 `codex_builtin` 输出新增 `expected_output: exactly_one_image` 与 `contract` 字段，把"一调用一图、禁止合并"从提示词约束升级为脚本下发的显式契约。
- [skill] 强化 `.agents/skills/generate-storyboard-prompts/SKILL.md` 与 `.agents/skills/generate-asset-prompts/SKILL.md`：新增"逐板隔离/逐资产隔离（强制）"，要求逐个 packet/资产生成独立提示词，禁止在一条提示词里描述多个 `SB###` 板或多个资产。

### Reason
- 生图环节此前缺少强制护栏：分镜板链路甚至没有单任务分发器，执行方直接面对整份 manifest，容易把所有分镜板、所有资产排版进同一张图，严重打乱生产节奏。本次通过"最小必要输入"原则——每次生图只暴露单个 `IMG-####` / `SB###` 的 `prompt_path`——从结构上根治批量合图。

### Compatibility
- 不改变阶段结构、DAG、schema 与审批动作，属纯护栏与文档加固。
- 旧 Run 无需迁移；新增脚本为可选分发器，不影响既有 `execute_image_queue.py` 流程。

### Validation
- `python scripts/validate_pipeline_contract.py`
- `python -m unittest discover -s tests -v`
- `python scripts/validate_project.py examples/minimal_run --level draft`
- `python scripts/check_document_references.py`
- `python scripts/check_repository_policy.py`

## 2026-08-03 - v8.1

### Changed
- [skill] 新增 `.agents/skills/advertising-idea-review/`（含 `SKILL.md`、`agents/openai.yaml`）与 `skills/raw_prompts/idea_review.source.md`：在 `idea_generation` 产出 `brief.md`/`story.md` 后、人工审批前自动执行八维创意审查（世界规则提取、内部逻辑、台词、人物、品牌必然性、情绪节奏、视听叙事、AI 制作优势、文化与伦理），对话中输出分级诊断报告，并把问题清单写入 `outputs/idea_review_feedback.md`。
- [process] 审查只出意见、不放行；放行永远由人工 `approve` / `reject` 决定。
- [process] `reject` 后进入修订轮：`advertising-idea-strategy` 自动读取 `outputs/idea_review_feedback.md` 逐条响应 P0/P1 问题，产出新 Artifact Revision；修订后不自动二次审查，仅在人工明确要求时重审（审查轮次 +1）。
- [process] `outputs/idea_review_feedback.md` 是流程状态文件：不进 Artifact/Approval Registry、不进最终包、不参与 `validate_project.py` 校验。
- [check] `validate_pipeline_contract.py` 的 orphan skill 白名单加入 `advertising-idea-review`（由 `run-ad-pipeline` 在审批前调用，不挂 stage executor）。
- [docs] 同步 README、`docs/flow.md`、`PIPELINE_FLOW.md`、`docs/quality_gate_matrix.md`、`docs/iteration_protocol.md`：审查回环 DAG、审批清单、产物目录、质量门矩阵。
- [tests] 新增 2 个回归测试：审查 skill 非 orphan、idea-strategy 修订模式已接线反馈文件。

### Reason
- 方案产出后缺少创意质量把关：下游 `style_bible`、分镜和全部提示词都从 `brief.md`/`story.md` 派生，逻辑断点、品牌虚假嵌入和情绪错位会被下游放大。现有审批只做非空检查，不审查创意质量。

### Compatibility
- 不改变阶段结构、不改变 `config/pipeline.yaml`、不升级 schema、不改变审批动作。
- 审查是可选项：不运行审查也可照常 `approve` 放行。
- 旧 Run 无需迁移。

### Validation
- `python scripts/validate_pipeline_contract.py`
- `python -m unittest discover -s tests -v`
- `python scripts/validate_project.py examples/minimal_run --level draft`
- `python scripts/check_document_references.py`
- `python scripts/check_repository_policy.py`

## 2026-08-03 - v8.0

### Changed
- [duration] `V###` 视频生成单元统一限制为 4–30 秒，PipelineSpec、Schema、Skill 和校验器共享相同边界。
- [aspect] 视频画幅未声明时默认 `16:9`，并写入分镜包、Video Prompt Manifest、提示词和最终生产包。
- [references] 视频模型参考缩减为分镜板、人物和广告商品；删除 `scene_assets`/`prop_assets`，新增 `product_assets`。
- [storyboard] 场景、构图、装饰、静态特效和广告文字全部在分镜板阶段固定。
- [text] `storyboard.json` 新增结构化 `advertising_text`；Board 审批要求逐字匹配并确认无额外文字，禁止后期补字回退。
- [assets] Prop 新增 `business_role`，只有 `advertised_product` 可以进入视频参考。
- [migration] 新增 V7→V8 dry-run/apply 迁移脚本和 `.v7.bak` 备份。
- [tests] 新增长度边界、默认画幅、场景污染、商品白名单、文字传播/审批和 V8 迁移回归测试。

### Compatibility
- V7 Run 必须执行 `migrate_run_v7_to_v8.py`；旧分镜、Board、Video Prompt 和最终包需要按 V8 语义复核或重建。 <!-- 已废弃：迁移脚本已移除，不再支持 V6/V7 迁入；本行为历史记录。 -->
- `video_prompt_manifest.json` 升级到 2.0，不再接受 `scene_assets` 和 `prop_assets`。

## 2026-08-01 - v7.0

### Changed
- [contracts] 将资产计划、资产媒体、Board 计划和 Board 媒体拆成不可变 Manifest，后续阶段不再写回上游计划。
- [approval] 所有媒体通过真实 Artifact Revision 审批；production 和打包会重新验证文件哈希与 Approval Registry。
- [pipeline] 每个阶段声明至少一个可追踪输出，checkpoint 阶段结构由 PipelineSpec 动态生成。
- [task] Stage Task 记录真实 Skill 路径、输入/输出 revision，并与 checkpoint 状态同步和幂等复用。
- [skills] 正式能力统一迁移到 `.agents/skills/<name>/SKILL.md`，删除旧式孤立 Skill 包装层。
- [cleanup] 删除旧 `video_prompts.json` Schema、示例和验证器，保留唯一 `video_prompt_manifest.json` 合同。
- [migration] 新增 V6→V7 dry-run/apply 迁移脚本和备份报告。
- [tests] 新增完整 Production/Delivery、媒体篡改、Board 重建、Task 同步和迁移回归测试。

### Compatibility
- V6 run 不再被运行时静默改写；必须先运行 `migrate_run_v6_to_v7.py`。 <!-- 已废弃：迁移脚本已移除，不再支持 V6/V7 迁入；本行为历史记录。 -->
- V7 最终包必须重新生成，不能复用 V6 package manifest。

### Validation
- `python scripts/validate_pipeline_contract.py`
- `python -m unittest discover -s tests -v`
- `python scripts/validate_project.py examples/minimal_run --level draft`

## 2026-08-01 - v6.0

### Changed
- [process] `config/pipeline.yaml` 成为阶段、依赖、executor、审批、skip 和产物的唯一事实源；运行时改为显式 DAG。
- [process] 恢复分镜审批；新增 hash 绑定的 Artifact Revision 与 Approval Registry。
- [process] 图片执行支持 `skipped` 草稿路径，但 production 禁止 `skip_effect=draft_only`。
- [outputs] 新增 `storyboard_board_manifest.json` 和 `video_prompt_manifest.json`，固定 V/SB/S 关系。
- [script] 新增 Pipeline Engine、确定性 Board/Video Manifest builder、媒体登记与审批工具。
- [script] 最终打包只消费 manifest，按视频携带正确 prompt/board/assets，并输出版本化 package 与完整 hash 清单。
- [validation] 改用标准 JSON Schema；校验分为 structure/draft/production/delivery；弃用并阻断歧义的 `--phase all`。
- [security] 模型或 manifest 提供的路径必须受限于 run 目录；资产图片使用稳定 asset_id 文件名。
- [ci] 修复 `.agents/skills/` 解析，安装锁定依赖并运行回归测试。

### Compatibility
- v4/v5 checkpoint 会在保存时升级到 PipelineSpec 版本，但旧项目需要生成 Board/Video Manifest 后才能通过 draft。
- `delivery_manifest.json` 不再是有效最终契约；统一使用 `final_package_manifest.json`。
- 自动生图被跳过的项目只能通过 draft，不能通过 production/delivery。

### Validation
- `python scripts/validate_pipeline_contract.py`
- `python -m unittest discover -s tests -v`
- `python scripts/validate_project.py examples/minimal_run --level draft`

## 2026-07-31 - v5.0

### Changed
- [skill] 视频提示词升级至 v5.0：新增全局设定公式（基础环境/视觉风格/镜头语言/主体造型/表演核心/禁止项）、时间戳分镜控制、动态禁止项触发表、7 维主体定义公式。
- [skill] 视频提示词输出结构改为三段：`素材：` / `提示词：` / `约束：`（替换旧的 `【自检通过项】/【资产声明区】/【中文视频提示词】`）。
- [skill] 新增单镜头/多镜头/时间戳分镜三种写作规则，按叙事复杂度和时长自动选择结构。
- [skill] 新增具象化转译规则（情绪→微表情、氛围→光影声音、事件→动作分解、关系→空间距离）。
- [skill] 内部自检项从 10 项扩展到 14 项。

## 2026-07-31 - v4.0

### Changed
- [process] 流程从 14 阶段（含 3 个 review）精简为 11 阶段：移除 storyboard_sequence_review、generated_asset_review、storyboard_visual_review。
- [process] 新增 video_segment_planner 阶段（在分镜板提示词之前），镜头合并逻辑上移至此阶段。
- [process] frame_role 在 video_segment_plan.json 中分配，不再在分镜板提示词或视频提示词中重新分配。
- [outputs] 分镜板提示词从单文件 `storyboard_prompts.md` 改为按 board_id 分文件 `outputs/storyboard_boards/SB###.md`（每板 ≤ 4 镜）。
- [outputs] 视频提示词从单文件 `video_prompts.md` 改为按 video_id 分文件 `outputs/video_prompts/V###.md`。
- [outputs] 人物资产图从 2x2 身份四宫格改为 21:9 转面参考图。
- [schema] 镜头组时长上限从 15 秒提升到 30 秒。
- [script] validate_project.py 全面重写：validate_storyboard_prompt_generation 改为校验 storyboard_boards/ 目录，validate_video_prompts 改为校验 video_prompts/ 目录，video_segment_plan 从可选改为强制。
- [script] 删除 validate_seedance_video_prompts.py（功能已合并到 validate_project.py）。
- [script] 删除 build_video_segment_candidates.py、migrate_checkpoint.py、build_storyboard_board_input.py（死代码）。
- [schema] 删除 7 个无引用的 schema（storyboard_sequence_review、storyboard_visual_review、continuity_report、generated_media_review、image_result_manifest、shot_result_manifest、voice_reference_manifest、generated_asset_review）。
- [templates] 删除全部 5 个 v3.0 模板文件。
- [skills] 删除 3 个 review skill 目录 + 根文件、storyboard_static_frame_variant.source.md、build_image_queue.md（死文件）。
- [docs] 删除 4 个过时文档（gap_audit、generated_media_review_protocol、generation_mode_protocol、storyboard_sequence_review_protocol）。
- [docs] 11 个文档批量更新 v4.0 路径和概念。
- [config] pipeline_runtime.py schema_version 从 "3.1" 更新为 "4.0"，移除 reviews/ 目录检查。
- [repo] .gitignore 删除 v3.0 编号路径忽略规则。

### Reason
- v3.0 流程中分镜板提示词阶段缺少镜头组规划前置，导致用户跑流程时跳过分镜板提示词直接进入视频提示词。
- review 阶段在实际广告生产中不必要，增加流程复杂度。
- 单文件输出难以管理多镜头组场景。

### Compatibility
- 旧 v3.0 产出的 `storyboard_prompts.md` 和 `video_prompts.md` 需迁移为目录结构。
- 旧 checkpoint.json 的 phase_order 需更新为 11 阶段。

### Validation
- `python scripts/validate_project.py examples/minimal_run --phase all` 全部通过。 <!-- 已废弃：`--phase all` 现会主动报错，请改用 `--level draft`；本行为历史记录，保留原貌。 -->

## 2026-07-10 - v1.0.4

### Changed
- [script] 加强 `scripts/validate_project.py`：支持 `exclusiveMinimum`，补充空/未知/重复 `source_shots` 防御，校验视频段时长必须等于 source shots 总和，并区分单镜头与合并策略。
- [script] 重写 `scripts/validate_seedance_video_prompts.py`，从旧 `outputs/05_video_prompts/shots/SHOT_XXX.md` 路径改为校验当前扁平产物 `outputs/video_prompts.md` 与 `outputs/video_prompts.json`。 <!-- 已废弃：该脚本后续已删除，视频提示词校验并入 validate_project.py 的 validate_video_prompts；本行为历史记录。 -->
- [schema] `storyboard.schema.json` 将 `duration_seconds` 收紧为 `>0` 且 `<=15`。
- [schema] `asset_manifest.schema.json` 将 `generation_required` 收紧为 boolean，避免字符串 `"true"` 造成假通过。
- [schema] 删除未被当前主流程使用且与 Skill 契约冲突的 `art_direction.schema.json` 和旧 `shot_video_prompt.schema.json`。
- [ci] GitHub Actions 同时编译两个校验器，并对 `examples/minimal_run` 执行主流程和视频提示词专项校验。
- [docs] 清理 README、质量门、迭代协议、一致性清单、仓库策略、资产引用规则和旧 loop 协议中的旧目录、旧 ID、旧阶段残留。
- [example] 对齐 `examples/minimal_run/checkpoint.json` 与 `checkpoint.template.json` 的结构。
- [repo] `.gitignore` 增加当前扁平 `outputs/*` 忽略规则。

### Reason
- 旧 13 阶段流程、`SHOT_XXX` 命名、`CHAR/ENV/PROP` 抽象 ID、旧 numbered outputs 目录和未实现的 final 阶段与当前 7 阶段扁平流程混用，容易导致维护者按旧文档生成当前校验器不认可的产物。
- 部分 schema 与校验器口径不一致，存在文件通过但内容不可生产的假通过风险。

### Compatibility
- 旧 `outputs/03_storyboard/`、`outputs/05_video_prompts/`、`SHOT_XXX` 和 `CHAR_001/ENV_001/PROP_001` 流程不再作为当前主流程维护。
- 旧项目若使用字符串形式的 `generation_required`，需要迁移为 JSON boolean。

### Validation
- CI 配置已更新为运行：`python scripts/validate_project.py examples/minimal_run --phase all` 和 `python scripts/validate_seedance_video_prompts.py examples/minimal_run`。 <!-- 已废弃：`--phase all` 现会报错、`validate_seedance_video_prompts.py` 已删除；当前 CI 见 .github/workflows；本行为历史记录。 -->

## 2026-07-04 - v1.0.3

### Changed
- [process] 简化第一阶段：`story_generation` 只输出 `outputs/story.md`，不再输出 `story.json` 或任何 story index。
- [process] 明确艺术总监先于导演出现，但只负责视觉方向；具体构图、景别、机位和镜头调度归 `storyboard_director`。
- [process] 沉淀人物状态资产规则：人物资产采用 `人物稳定名_状态`，例如 `林小满_雨夜接电话状态`。
- [process] 明确人物资产生产为一张 21:9 人物状态资产图，可在同一张图里包含特写、正面、侧面、后视图。
- [process] 简化资产提示词生成输入：使用 `story.md + style_bible.md + asset_type + asset_name + output_prompt_path`。
- [process] 增加分镜参考图规则：每个 `S###` 必须声明 `recommended_frame_role`，并判断是否引用上一分镜图片作为站位参考。
- [process] 沉淀视频分镜合并规则：合并对象是连续 `S###`，不是 `SC###`；同一 `scene_id` 内连续分镜且总时长 `<=15s` 才允许合并。
- [process] 明确视频提示词阶段必须输出 `frame_references`，说明每张分镜图在 `V###` 中承担首帧、尾帧或关键帧角色。
- [skill] 将 `image_generation_executor` 升级到 1.3.0：改为单资产图片执行契约。
- [skill] 将 `video_prompt_generator` 升级到 2.6.0：吸收最新中文视频提示词规则，新增锁定与补足、镜头可见、具象化转译、单运镜纯度和三段输出格式。
- [prompt] 更新 `skills/raw_prompts/seedance_video_prompt.source.md`。
- [script] `validate_project.py` 只校验当前生产链路。
- [schema] `video_prompt.schema.json` 只保留当前流水线视频生成计划。
- [docs] 更新 README、flow、local run 模板和质量门。
- [examples] 更新 `examples/minimal_run/`。

### Reason
- 资产提示词生成需要完整剧本上下文，否则人物、场景和道具只剩孤立名称，难以做准设定。
- 视频提示词必须把抽象情绪、氛围和事件转译为可见动作、光影、声音和空间关系，避免文学化描述。
- 强连续动作如果拆成多次生成，容易造成动作、手部、道具位置和人物姿态穿帮，因此在同场景且总时长不超过 15 秒时应优先合并。

### Validation
- 待 CI 验证：`python scripts/validate_project.py examples/minimal_run --phase all`。

## 2026-07-04 - v1.0.2

### Changed
- [ci] 新增 GitHub Actions workflow：编译 `scripts/validate_project.py`、解析 `checkpoint.template.json` 与全部 schema JSON、运行最小样例 `examples/minimal_run --phase all`。
- [examples] 新增 `examples/minimal_run/`，提供一套可跑通的最小本地 run，用作回归测试基线。
- [schema] 扩展 `schemas/video_prompt.schema.json`，要求 `video_prompts.json` 输出结构化 `V###` 计划。
- [script] `validate_project.py` 新增 `video_prompts.json` 校验。

### Reason
- 仅有 Markdown 提示词无法可靠校验 shot 覆盖、任务类型、操作对象和素材声明关系；结构化 JSON 可作为机器可验证的生产计划。

### Validation
- 已用本地最小样例跑通 `python scripts/validate_project.py examples/minimal_run --phase all`。

## 2026-07-04 - v1.0.1

### Changed
- [skill] 将 `video_prompt_generator` 升级到 2.1.0，补入早期 Seedance 视频提示词规则。

### Validation
- 已在本地构建新版 `validate_project.py` 并通过 Python 语法编译检查。

## 2026-07-04 - v1.0.0

### Changed
- [process] 将旧 13 阶段流程重构为 7 阶段即梦画布前置流程：`story_generation` → `art_direction` → `storyboard_director` → `asset_executor` → `asset_prompt_generation` → `storyboard_prompt_generator` → `video_prompt_generator`。
- [outputs] 将本地 run 输出目录改为扁平结构。
- [script] 重写 `validate_project.py`，按新扁平目录和新 schema 校验。
