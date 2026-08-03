# Repository Policy

提交前必须运行：

```text
python scripts/check_repository_policy.py
```

该检查阻止 `local_runs/`、根级 `outputs/`、非示例媒体文件和疑似硬编码密钥进入仓库。真实剧本、品牌素材、生成图片、生成视频、日志和 checkpoint 只属于本地 run。

## 核心边界

仓库只保存可复用、可迁移、可迭代的流程资产。每天创作沉淀下来的故事、分镜、图片、视频、参考素材、日志和运行状态属于本地资源，不上传仓库。

CodeX 可以作为图片生成执行环境，但必须由用户在每次图片阶段明确选择。无论图片是在 CodeX 内部生成还是外部生成，生成图片都属于本地 run 资源，不上传仓库。

CodeX 不作为视频生成或剪辑执行环境。视频生成、剪映剪辑只生成提示词、交接材料和状态记录。

## 应该提交到仓库

- `README.md`：主流程说明。
- `.agents/skills/*/SKILL.md`：正式 Skill 合同。
- `skills/raw_prompts/*.source.md`：已确认可复用的源提示词。
- `config/pipeline.yaml` 或 `config/config.example.yaml`：非敏感默认配置。
- `checkpoint.template.json`：运行状态模板。
- `inputs/*.template.md`：输入模板。
- `docs/*.md`：流程文档、迭代规则、字段说明。
- `checks/*.md`：一致性检查清单。
- `schemas/*.json`：当前主流程实际使用的数据结构规范。
- `templates/*.template.*`：可复用的状态表、交接表、运行记录模板。
- `scripts/*.py` / `scripts/*.ps1`：初始化、校验、拆分提示词等可复用脚本。
- `examples/`：小体量、脱敏、可复现的示例。
- `.github/workflows/*.yml`：仓库级 CI 校验。

## 不应该提交到仓库

- `checkpoint.json`：本地运行状态。
- `local_runs/`、`creative_runs/`、`runs/`：每日创作沉淀。
- 真实项目的 `outputs/` 产物，包括故事、风格圣经、分镜、资产清单、提示词、参考图和生成结果。
- 参考图片、视频、音频、生成图、生成视频、剪辑工程。
- 真实项目的人物资产图、场景资产图、道具资产图和分镜参考图。
- API key、cookie、token、本地服务地址、个人账号信息。
- 大体积媒体文件和未经授权的参考素材。
- 某个客户、品牌或个人项目的私有内容。

## 本地目录建议

每天的创作统一放在本地忽略目录：

```text
local_runs/
└── 2026-06-13/
    └── project_slug/
        ├── inputs/
        │   └── idea_brief.md
        ├── outputs/
        │   ├── story.md
        │   ├── style_bible.md
        │   ├── storyboard.json
        │   ├── asset_manifest.json
        │   ├── shot_asset_map.json
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

`project_slug` 使用英文小写、数字和短横线，例如 `lonely-robot-rainy-city`。

## 可迁移原则

另一台电脑 clone 仓库后，只需要：

1. 执行 `scripts/init_local_run.ps1 -ProjectSlug project-slug`。
2. 填写生成的 `local_runs/YYYY-MM-DD/project_slug/inputs/idea_brief.md`。
3. 如使用外部 provider，通过本地环境变量配置凭据；仓库不保存本地密钥配置。
4. 运行 `python scripts/validate_project.py local_runs/YYYY-MM-DD/project_slug --phase initialized`。
5. 按 `README.md` 和 `docs/flow.md` 运行流程。

不要手工复制 `checkpoint.template.json` 作为正式 checkpoint；初始化脚本会写入真实 `project_slug`、创建时间和 run 路径。

## 版本原则

- 源提示词进入仓库后，按版本演进，不直接覆盖历史语义。
- 大改 Skill 输入输出时，必须同步更新 `config/pipeline.yaml`、`docs/flow.md`、`README.md` 和 `checks/consistency_checklist.md`。
- 每次流程迭代要写入 `docs/iteration_protocol.md` 定义的变更记录。

## 文字类画面原则

文字类画面仍应生成图片，例如作文本、纸条、警号、通知、票据、贺卡。仓库只保存这类画面的提示词规则和模板，不保存具体项目生成图。
