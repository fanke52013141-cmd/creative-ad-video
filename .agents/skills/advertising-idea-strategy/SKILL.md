---
name: advertising-idea-strategy
description: Turn a vague advertising brief, product facts, audience, and brand context into a structured creative brief. Use before content strategy to decide what to shoot before how to shoot it. Do not write the full script, storyboard, or prompts.
---

# Advertising idea strategy

## Position in the pipeline

Run first. Decide the creative direction: what the ad is about, who it targets, what the core hook is. Do not write the script, the storyboard, or any prompts.

## Inputs

- 用户想法（直接对话或文档）：一句话想法、一个产品介绍、或一场广告比赛活动说明
- 用户补充资料（可选）：产品资料、品牌资料、参考视频、目标受众画像、投放平台
- `config/verticals/advertising.yaml`：广告的生产参数（目标时长、画幅等默认值）

## Output

Write `outputs/brief.md` — 创意简报。

## Creative brief structure

```markdown
# 创意简报

## 核心创意
[一句话核心创意]

## 创意类型
广告

## 主角设定
- 身份：
- 欲望：
- 弱点：

## 核心冲突
[主角面对的核心问题]

## 情绪方向
[观众看完后的感受]

## 目标受众
[谁会看这个视频]

## 目标平台
[抖音 / 视频号 / 小红书 / B站]

## 画幅比例
[9:16 / 16:9 / 1:1]

## 目标时长
[例如：30秒 / 60秒 / 90秒]

## 商业元素
- 产品/品牌：
- 核心卖点：
- CTA：
- 证据/支撑：

## 禁用元素
[不能出现的内容]

## 参考
[影片/图片/风格参考]
```

## Procedure

1. 读取用户想法和补充资料。
2. 提炼核心创意：这条广告要让观众感受到什么或做出什么动作？
3. 识别主角（如有）、其欲望、弱点、核心冲突。
4. 定义情绪方向。
5. 整合商业元素：产品、核心卖点、CTA、可用证据。
6. 记录目标受众、平台、画幅、时长（从用户输入或 advertising.yaml 默认值）。
7. 列出禁用元素和参考。
8. 信息缺失时，最多问 2 个高信息增益问题后再写简报。
9. 写 `outputs/brief.md`。

## Boundary

- 不写完整剧本（那是 content_strategy 的职责）
- 不写分镜、镜头、资产、提示词
- 不编造用户未提供的产品 claims、价格、证据
- 简报决定"拍什么"，不决定"怎么拍"

## Quality gate

- 核心创意一句话清晰
- 主角（或产品作为主角）有明确欲望
- 商业元素（产品、卖点、CTA、证据）齐备或标记"待确认"
- 目标受众、平台、时长、画幅明确
- 没有剧本、分镜、提示词内容泄漏
