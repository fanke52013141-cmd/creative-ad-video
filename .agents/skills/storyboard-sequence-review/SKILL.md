---
name: storyboard-sequence-review
description: Review a complete storyboard sequence before asset production for real shot boundaries, duration, causality, character, prop, space, eyeline and screen-direction continuity. Runs after storyboard_director and before asset_executor. Blocks asset production when P0 issues (cannot cut or generate coherently) are unresolved. Does not generate storyboard images or rewrite the story.
---

# 分镜序列审查

## 流程定位

在 `storyboard_director` 产出 `outputs/storyboard.json` 之后、`asset_executor` 之前运行。检查分镜能否稳定进入 AI 视频生产：发现会导致穿帮、跳戏、视频生成跑偏的问题，并给出可执行修正建议。

审查不是重新创作分镜，而是守住三个硬规则：

1. **单镜头时长不得超过 `MAX_SHOT_DURATION`（10 秒，见 `storyboard.schema.json`）**，且与目标总时长一致。
2. **分镜必须是真实镜头边界**，不得把一个连续镜头硬拆成多份（同一机位、同一景别、同一空间、同一连续动作拆成多个 shot，AI 独立生成时会出现角色/场景/光线/道具位置不一致）。
3. **抽象词必须转译为画面证据**，不得裸写情绪、氛围、事件或人物关系；AI 无法从抽象词稳定生成微表情、动作、空间关系和光影证据。

## 输入（读文件，不审查对话里的方案）

- `outputs/storyboard.json`：待审查分镜（必读）。
- `outputs/story.md`：广告剧本（参照因果、人物状态、时间线）。
- `outputs/style_bible.md`：视觉边界（参照光线、风格、道具）。

审查前**必须读取以上文件的实际内容**。

## 输出

写 `outputs/reviews/storyboard_sequence_review.json`，符合 `schemas/storyboard_sequence_review.schema.json`：

- `status`：`pass`（无未解决 P0）或 `revise_required`（存在 P0）。
- `checked_shots`：覆盖全部 `S###`。
- `issues[]`：每条含 `severity`（P0/P1/P2）、`category`、`shot_ids`、`description`、`fix_suggestion`。
- `p0_count` / `p1_count` / `p2_count`。

## 审查方法

1. **单镜头（1-shot）**：逐 shot 检查时长、可见动作、叙事功能、镜头边界理由、抽象词是否落地为画面证据。
2. **相邻镜头（2-shot）**：检查动作阶段、站位、视线方向、屏幕方向、道具、因果是否承接；是否存在连续镜头硬拆和抽象情绪跳变。
3. **三镜头（3-shot）**：检查局部逻辑、反应时机、空间理解。
4. **全片（sequence）**：检查时间线、人物持续状态变体、场景结构、母题、情绪节奏。

## 严重度分级

- **P0**：无法剪辑或无法连贯生成，必须阻止下游工作。`status` 必须为 `revise_required`。
- **P1**：有实质风险；若修正不破坏导演意图可自动修订，否则标记待人工确认。
- **P2**：安全的生产备注。

## 边界

- 只评判已有分镜，不重写分镜、不生成分镜图、不写资产清单、不写图片/视频提示词。
- 不修改 `outputs/storyboard.json`；只写 `outputs/reviews/storyboard_sequence_review.json`。
- 审查 JSON 是流程状态：注册为 Artifact Revision，但不放行任何审批（放行仍由 `approve` 决定）。

## 质量门

- 1-shot 检查必须覆盖每个 shot 恰好一次；2-shot 覆盖所有相邻对；3-shot 覆盖所有可用三镜头窗口。
- 每条 issue 都给出 shot ID、证据、最小可执行的修复方向。
- 只有无未解决 P0 时才返回 `status: pass`。
- 输出必须通过 `schemas/storyboard_sequence_review.schema.json` 校验。
