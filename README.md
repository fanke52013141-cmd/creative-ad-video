# Video Flow

基于 creative-ad-video V8 重构的视频创作执行标准。原项目保留在本仓库的旧命令中，新流程从 `python -m video_flow` 进入；二者状态不可混用。

## 首版能力

支持品牌/转化广告和单篇艺术、娱乐、公共表达短片，写实风格，交付前期文本包。主Agent协调；专业子Agent以新上下文处理指定任务；独立review后接受产物。阶段与依赖只有config/workflow.yaml一份定义。

包含多维路由、锁定Skill快照、输入版本/hash、真实agent ID绑定、回执校验、审查覆盖、修订预算、批准门禁、上下游失效、并发锁和交付清单。

连载、长片、纪录片、其他风格与真实媒体生成尚未开放；未知路线明确阻断。广告/短片/分镜专业包的建设与评估状态记录在各自package.json，其他支撑Skill为基础版，不冒称已完成全部专业深度。

## 开始

```powershell
python -m pip install -r requirements.txt
$env:PYTHONUTF8='1'
python -m video_flow doctor
python -m video_flow init ../video-flow-runs/demo --brief examples/video_flow/coffee-brief.json
python -m video_flow status ../video-flow-runs/demo
python -m video_flow dispatch ../video-flow-runs/demo story
```

然后由Codex主Agent按 [适配说明](adapters/codex.md) spawn新上下文工作者、bind真实ID、等待并submit。CLI本身不能启动聊天中的子Agent；输出task packet仅代表待执行。使用 `$run-video-flow` 可以让接入本仓库的Agent遵循该流程。

`init --media` 在文本阶段后加入参考媒体扇出阶段（asset_media 逐资产、board_media 逐场板）。一次dispatch一个item，任务包只含该项切片与全局约束；工作者按 [单项媒体协议](.agents/skills/generate-media/SKILL.md) 一任务一图，全部完成后汇总为带哈希的媒体清单并独立评审；revise与invalidate均可只作用于单个item。

默认剧本、风格与分镜通过独立质量检查后仍需用户批准；展示具体作品取得决定，再运行approve。启动时可明确选择 `--approval automatic`，独立质量审查仍保留。局部创作修订用invalidate；初始需求变更创建新run，避免改写锁定事实。

```powershell
python -m video_flow bind RUN TASK_ID ACTUAL_AGENT_ID
python -m video_flow submit RUN TASK_ID
python -m video_flow approve RUN story_review --actor USER --reason '用户对该版本的具体批准'
python -m video_flow retry RUN TASK_ID --reason '工具失败或缺失输入'
python -m video_flow invalidate RUN story --reason '创作修订原因'
python -m video_flow package RUN
```

[任务契约](docs/contracts.md) 说明候选、审查与回执。所有run应置于仓库外；不向框架提交客户资料。

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
