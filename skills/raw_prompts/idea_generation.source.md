# Idea generation (default)

## Position in the pipeline

Run after `idea_brief.md` is filled and before `content_strategy`. Decide the creative direction: what the video is about, who it targets, what the core hook is. Do not write the script, the storyboard, or any prompts.

## Inputs

- `inputs/idea_brief.md`: user's raw idea, possibly very vague.
- User-provided context, audience, platform, duration, and references.
- Active vertical config under `config/verticals/`.

## Output

Write `outputs/brief.md` — a creative brief that the downstream `content_strategy` Skill will turn into a full script.

## What the creative brief must contain

```markdown
# 创意简报

## 核心创意
[一句话核心创意]

## 创意类型
[广告 / 剧情 / IP短视频 / 其他]

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
- 产品/品牌：（非广告可留空）
- 核心卖点：
- CTA：
- 证据/支撑：

## 禁用元素
[不能出现的内容]

## 参考
[影片/图片/风格参考]
```

## Procedure

1. Read `idea_brief.md` and any user-provided context, audience, and reference materials.
2. Extract the core creative direction: what is the one thing this video should make the audience feel or do?
3. Identify the protagonist (if any), their desire, their weakness, and the core conflict.
4. Define the emotional direction the audience should feel after watching.
5. Record commercial elements if applicable (product, selling point, CTA, evidence); leave blank for non-commercial types.
6. Record target audience, platform, aspect ratio, and duration from the brief or vertical config defaults.
7. List any禁用元素 and references.
8. If information is missing, ask at most 2 high-impact questions before writing the brief.
9. Write `outputs/brief.md`.

## Boundary

- Do NOT write the full script — that is `content_strategy`'s job.
- Do NOT write storyboard, shots, assets, or prompts.
- The brief decides "what to shoot", not "how to shoot it".

## Quality gate

- Core creative direction is clear in one sentence.
- Protagonist (or subject) has a clear desire.
- Target audience, platform, duration, and aspect ratio are explicit.
- No script, storyboard, or prompt content leaked into the brief.
