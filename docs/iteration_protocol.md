# Iteration Protocol

## 迭代类型

| 类型 | 说明 | 是否提交仓库 |
| -- | -- | -- |
| `process` | 流程结构、阶段顺序、Skill 边界变化 | 是 |
| `skill` | Skill 包装层或源提示词版本变化 | 是 |
| `schema` | JSON 字段、产物结构变化 | 是 |
| `config` | 默认配置、路径、模型参数模板变化 | 是，不含密钥 |
| `check` | 质量门、检查清单、审查规则变化 | 是 |
| `example` | 脱敏小样例 | 可选 |
| `run` | 某一天某个短片的真实创作结果 | 否 |
| `asset` | 图片、视频、音频、参考素材、生成素材 | 否 |
| `generation_mode` | 内部/外部图片生成分支规则、状态字段、交接模板 | 是 |
| `prompt_output_contract` | 提示词输出语言、资产声明规则、复制格式 | 是 |
| `phase_state` | checkpoint 阶段状态机、完成状态、已知缺口/阻塞项 | 是 |
| `secret` | token、API key、cookie、本地账号信息 | 否 |

## 当前主流程

仓库当前主流程为 11 阶段扁平产物链：

```text
idea_generation
→ art_direction
→ storyboard_director
→ asset_executor
→ asset_prompt_generation
→ asset_image_generation
→ video_segment_planning
→ storyboard_prompt_generation
→ storyboard_image_generation
→ video_prompt_generation
→ final_package
```

当前主流程的本地输出目录为：

```text
outputs/
├── story.md
├── style_bible.md
├── storyboard.json
├── asset_manifest.json
├── shot_asset_map.json
├── video_segment_plan.json
├── storyboard_boards/
├── video_prompts/
│   └── V###.md
└── assets/
    ├── characters/
    ├── scenes/
    └── props/
```

不要在当前主流程文档中重新引入旧的 numbered outputs：`outputs/01_story/` 到 `outputs/07_final_delivery/`。

## 每日创作迭代

每日真实创作不直接改变仓库，先沉淀到本地：

```text
local_runs/YYYY-MM-DD/project_slug/
```

每个本地创作项目建议包含：

```text
project_slug/
├── inputs/
│   └── idea_brief.md
├── outputs/
│   ├── story.md
│   ├── style_bible.md
│   ├── storyboard.json
│   ├── asset_manifest.json
│   ├── shot_asset_map.json
│   ├── video_segment_plan.json
│   ├── storyboard_boards/
│   ├── video_prompts/
│   │   └── V###.md
│   └── assets/
│       ├── characters/
│       ├── scenes/
│       └── props/
├── references/
├── logs/
├── checkpoint.json
└── notes.md
```

## 从本地创作反哺仓库

只有当本地创作暴露出可复用问题时，才进入仓库迭代。

可反哺内容：

- 某个 Skill 的输入输出边界不清，需要调整包装层。
- 某个质量门漏掉了常见错误，需要加入检查清单或校验脚本。
- 某个资产字段经常缺失，需要升级 schema。
- 某个流程阶段顺序不合理，需要更新 README、`docs/flow.md` 和 `config/pipeline.yaml`。
- 某个提示词经过多次验证后变成稳定版本，需要升级源提示词。
- 内部/外部生成模式的分支规则需要更新。
- 视频提示词白名单需要更新；V8 当前固定为 Board、Character 和 advertised Product，不允许普通 `@PROP` 或 Scene。
- 分镜图引用、首帧/尾帧/关键帧角色或合并策略需要升级。
- 单次项目中暴露出的年代准确性、文字生成、镜头秒数等通用问题。

不可反哺内容：

- 某个具体故事本身。
- 某个客户项目素材。
- 某次生成的视频、图片、音频。
- 未脱敏的真实 reference。
- 剪映工程文件或外部平台生成记录原件。
- 某个 shot 的具体成片文件、失败版本、平台下载链接。

## 应该迭代哪些文件

当问题属于可复用流程时，优先迭代以下文件：

| 问题类型 | 优先修改文件 |
|---|---|
| 阶段顺序、分支选择、人工确认点 | `README.md`, `docs/flow.md`, `config/pipeline.yaml`, `checkpoint.template.json` |
| Skill 输入输出边界 | `.agents/skills/*/SKILL.md`, Skill `references/`, `config/pipeline.yaml` |
| 视频提示词格式、只输出中文、资产声明规则 | `.agents/skills/generate-video-prompts/`, `skills/raw_prompts/seedance_video_prompt.source.md`, `schemas/video_prompt_manifest.schema.json` |
| 分镜提示词帧角色和站位锚点 | `.agents/skills/generate-storyboard-prompts/`, `docs/flow.md`, `scripts/validate_project.py` |
| 人物、场景、道具资产命名 | `.agents/skills/plan-ad-assets/`, `schemas/asset_manifest.schema.json`, `schemas/shot_asset_map.schema.json` |
| 内部/外部图片生成分支 | `.agents/skills/fulfill-image-generation/`, `config/pipeline.yaml`, `checkpoint.template.json` |
| Schema 契约 | `schemas/*.json`, `scripts/validate_project.py` |
| 阶段状态机 | `checkpoint.template.json`, `docs/phase_state_machine.md`, `docs/flow.md` |
| 仓库提交边界 | `docs/repository_policy.md`, `.gitignore` |
| 质量检查 | `checks/consistency_checklist.md`, `scripts/validate_project.py`, `.github/workflows/validate.yml` |
| 默认参数或版本号 | `config/pipeline.yaml`, `CHANGELOG.md` |

当问题只属于某个单次视频项目时，只更新该项目的 `local_runs/YYYY-MM-DD/project_slug/`，不要改仓库流程文件。

## 单次仓库迭代格式

每次仓库迭代建议新增一条变更记录：

```markdown
## YYYY-MM-DD - vX.Y.Z

### Changed
- [process|skill|schema|config|check] 变更内容。

### Reason
- 这次变更从哪个本地创作问题中抽象出来。

### Compatibility
- 是否影响旧项目。
- 是否需要迁移字段或重跑阶段。

### Validation
- 用哪个本地项目或示例验证过。
```

## 版本号规则

- `MAJOR`：流程阶段、核心数据结构或 Skill 契约不兼容变化。
- `MINOR`：新增 Skill、字段、检查项，保持兼容。
- `PATCH`：文档、措辞、默认参数、小修复。

## 提交前检查

- [ ] 本次提交不包含 `local_runs/`、真实 `outputs/`、参考素材或生成媒体。
- [ ] 本次提交不包含密钥、账号信息或本地路径。
- [ ] 如果改了 Skill 合同，已更新对应 Skill、PipelineSpec 和回归测试。
- [ ] 如果改了数据结构，已更新 schema 或文档。
- [ ] 如果改了流程顺序，已更新 README、`docs/flow.md` 和 `config/pipeline.yaml`。
- [ ] 如果本次变化来自真实项目，已脱敏并抽象成通用规则。
