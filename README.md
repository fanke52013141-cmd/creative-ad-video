# Video Flow

基于 creative-ad-video V8 重构的视频创作执行标准。原项目保留在本仓库的旧命令中，新流程从 `python -m video_flow` 进入；二者状态不可混用。

## v0.2 制作包入口

当前为离线核心可用版本，完整优化尚未结束。已实现范围、验证口径与待完成事项见[更新状态说明](docs/v02-release-status.md)。

通过 `--production-config` 启用18阶段制作流程：剧本、详细分镜、人物/场景/物品参考图、分镜板、按平台生成片段组织的视频提示词，以及可独立校验的TXT与图片交付包。旧run沿用已锁定版本；不带该参数时维持原有流程。

```powershell
$env:PYTHONUTF8='1'
python -m video_flow init ../video-flow-runs/my-production --brief examples/v02/brief.json --media --production-config config/production.example.yaml
python -m video_flow preflight ../video-flow-runs/my-production
python -m video_flow status ../video-flow-runs/my-production
```

默认配置使用本地图片导入，Seedance参数来自用户提供手册，状态为user_supplied。当前v0.2自动生图适配未接入，generate模式明确阻断；测试配置仅用于无网络的合成媒体，不可作为正式画面。专业工作仍由宿主协调，详见 [v0.2契约](docs/contracts-v02.md)。

```powershell
# 首次剧本任务派发前可登记已有剧本，作者转换后仍需独立审查
python -m video_flow import-input RUN --kind story --file PATH_TO_STORY_TXT
# 素材需求就绪后，按reference_key导入图片；板图用 --stage board_media
python -m video_flow import-media RUN --reference-key CHAR001.work.front --file PATH_TO_PNG
# 查看局部修订将影响哪些板图和生成片段
python -m video_flow impact RUN --reference-key CHAR001.work.front
# 所有阶段接受后导出到一个尚不存在的目录
python -m video_flow validate RUN --scope delivery
python -m video_flow package RUN --format external-production --out NEW_PACKAGE_DIRECTORY
python -m video_flow verify-package NEW_PACKAGE_DIRECTORY
```

交付目录包含 `剧本.txt`、`详细分镜.txt`、`交付清单.txt`、三个资产文件夹和 `分镜板/V###/` 内的板图、参考映射TXT、视频提示词TXT。复制到新目录后可独立验证。平台实际标签在上传后核对，外部视频效果保持unverified。

可复现合成样例（目标目录必须不存在；图片为协议测试色块）：

```powershell
$env:PYTHONPATH='.'
python tests/test_v02_pipeline.py --write-f01 ../video-flow-runs/v02-synthetic-F01
```

合成样例验证文件、依赖、返修与交付；真实视觉评审和新宿主端到端试用单独登记。DeepSeek适配步骤见 [接入清单](adapters/deepseek-harness.md)，尚未标记已验证。

## 原有入口能力

支持品牌/转化广告和单篇艺术、娱乐、公共表达短片，写实风格，交付前期文本包。主Agent协调；专业子Agent以新上下文处理指定任务；独立review后接受产物。阶段与依赖只有config/workflow.yaml一份定义。

包含多维路由、锁定Skill快照、输入版本/hash、真实agent ID绑定、回执校验、审查覆盖、修订预算、批准门禁、上下游失效、并发锁和交付清单。

连载、长片、纪录片、其他风格与真实媒体生成尚未开放；未知路线明确阻断。广告/短片/分镜专业包的建设与评估状态记录在各自package.json，其他支撑Skill为基础版，不冒称已完成全部专业深度。

## 开始

```powershell
python -m pip install -r requirements.txt
$env:PYTHONUTF8='1'
python -m video_flow protocol
python -m video_flow doctor
python -m video_flow init ../video-flow-runs/demo --brief examples/video_flow/coffee-brief.json
python -m video_flow status ../video-flow-runs/demo
python -m video_flow dispatch ../video-flow-runs/demo story
```

然后由Codex主Agent按 [适配说明](adapters/codex.md) spawn新上下文工作者、bind真实ID、等待并submit。CLI本身不能启动聊天中的子Agent；输出task packet仅代表待执行。使用 `$run-video-flow` 可以让接入本仓库的Agent遵循该流程。

`init --media` 在文本阶段后加入参考媒体扇出阶段（asset_media 逐资产、board_media 逐场板、video_prompts 逐镜）。一次dispatch一个item，任务包只含该项切片与全局约束；图像工作者按 [单项媒体协议](.agents/skills/generate-media/SKILL.md) 一任务一图，提示词方法按条目类别分派专业知识包（[角色视觉设计](.agents/skills/character-visual-design/SKILL.md) / [场景视觉设计](.agents/skills/scene-visual-design/SKILL.md) / [分镜板提示词](.agents/skills/storyboard-panel-prompts/SKILL.md)），逐镜视频提示词使用 [视频镜头提示词](.agents/skills/video-shot-prompts/SKILL.md)。全部完成后汇总为带哈希的清单并独立评审；revise与invalidate均可只作用于单个item。

默认剧本、风格与分镜通过独立质量检查后仍需用户批准；展示具体作品取得决定，再运行approve。启动时可明确选择 `--approval automatic`，独立质量审查仍保留。局部创作修订用invalidate；初始需求变更创建新run，避免改写锁定事实。

```powershell
python -m video_flow bind RUN TASK_ID ACTUAL_AGENT_ID
python -m video_flow submit RUN TASK_ID
python -m video_flow approve RUN story_review --actor USER --reason '用户对该版本的具体批准'
python -m video_flow retry RUN TASK_ID --reason '工具失败或缺失输入'
python -m video_flow invalidate RUN story --reason '创作修订原因'
python -m video_flow package RUN
```

[任务契约](docs/contracts.md) 说明候选、审查与回执。所有run应置于仓库外；不向框架提交客户资料。接入的协调Agent必须先执行 `python -m video_flow protocol` 并遵守其步骤与禁项；任何 run 事后可执行 `python -m video_flow audit RUN` 取证核验（哈希链、回执、契约重放、作者/评审隔离、工作目录卫生）——验收级机制能发现违规，强阻止需宿主权限隔离。

## 验证

```powershell
$env:PYTHONUTF8='1'
python -m unittest discover -s tests -v
python -m video_flow doctor
python scripts/validate_pipeline_contract.py
python scripts/check_document_references.py
```

单元测试用合成角色/产物检验执行协议；不能据此宣称创作质量优秀。实际子Agent的试用记录另存docs/development-status.md。

## 强制边界

本地实现属于验收级：能够拒绝越阶段、错误回执、空审查、严重缺陷和失效版本；agent ID与actor是审计标签。全盘访问权限下的Agent仍可篡改本地文件。强制身份隔离需由宿主提供独立权限与批准工具，不由文档宣称实现。

原广告V8流程与约束见 [旧版说明](docs/legacy-advertising-readme.md) 和 [旧版规则](docs/legacy-advertising-rules.md)。保留其版本/媒体交付能力；修复了序列审查pass标签跳过严重问题与覆盖检查的缺口。

来源仓库：https://github.com/fanke52013141-cmd/creative-ad-video ，基线commit 5b86a5d44185ac580d2d806411f7628a18ec6d7e。此工作目录保留继承Git历史，reference指向本地参考副本，没有配置发布远程。
