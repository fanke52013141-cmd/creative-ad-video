---
name: advertising-idea-review
description: Review an ad brief and script (outputs/brief.md and outputs/story.md) before human approval. Extracts the ad's world rule, runs an eight-dimension structural review (logic, dialogue, character, brand necessity, emotion pacing, audiovisual function, AI-production leverage, culture/ethics), presents a graded diagnosis in conversation, and writes a machine-readable issue list to outputs/idea_review_feedback.md for the revision loop. Only advises; it never approves or blocks.
---

# 广告方案审查

## 流程定位

在 `idea_generation` 产出 `outputs/brief.md` 与 `outputs/story.md` 之后、人工审批（`approve` / `reject`）之前运行。审查只出意见、不放行；放行永远由人工在 `run_pipeline.py` 决定。

完整方法论（世界规则提取、八维审查、分级诊断、反馈文件格式）见 `skills/raw_prompts/idea_review.source.md`，本文件只定义输入、输出与边界。

## 输入（读文件，不审查对话里的方案）

- `outputs/brief.md`：创意简报。
- `outputs/story.md`：广告剧本。
- 可选：`outputs/idea_review_feedback.md`（存在时表示二次审查，先对照上一轮问题清单确认已修复项，审查轮次 +1）。

审查前**必须读取这三份文件的实际内容**。

## 输出

1. **诊断报告**：按 `skills/raw_prompts/idea_review.source.md` 的 `<OutputFormat>` 在对话中呈现（世界规则 → 🔴致命 / 🟡重要 / ⚪一般 / ✅值得保留 → 优先修改顺序 → AI优势放大建议）。
2. **反馈文件**：按 `<FeedbackFile>` 写入 `outputs/idea_review_feedback.md`，供修订轮 `advertising-idea-strategy` 自动读取。含审查轮次、审查对象修订、P0/P1/P2 问题清单、值得保留、修订要求。**不含审查结论**。

## 边界

- 只评判已有内容，不主动重写方案。
- 不放行、不拦截：不产生 approved/rejected 审批结论。
- 不写正式分镜、不拆资产、不写图片/视频提示词。
- 不修改 `outputs/brief.md`、`outputs/story.md`；只写 `outputs/idea_review_feedback.md`。
- 反馈文件是流程状态，不是交付产物：不进 Artifact Registry、不参与审批校验。

## 质量门

- 必须先提取并陈述「世界规则」，再用该规则审查，绝不用现实常识评判荒诞设定。
- 绝不以「画面很难实现」为由否定创意；只问「有没有用足 AI 制作优势」。
- 每条问题都附带「为什么是问题」+「一个可执行的修复方向」，控制在 3 句以内。
- 反馈文件必须包含：审查轮次、审查对象修订、P0/P1/P2、值得保留、修订要求。
- 审查范围有局部指定时，只输出指定维度，不空话填充。
