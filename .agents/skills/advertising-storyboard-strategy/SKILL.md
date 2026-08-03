---
name: advertising-storyboard-strategy
description: Convert an approved ad script and style bible into shot-level storyboard JSON with timing, generatable actions and explicit advertising text placement. Decide shot-by-shot how to shoot the ad; do not generate images, asset prompts or final video prompts.
---

# 广告分镜导演

## 流程定位

在广告艺术方向（advertising-art-direction）确认后、资产执行之前的环节。把广告剧本和视觉圣经转化为可直接执行的镜头序列 `storyboard.json`。完整方法论（广告节拍拆分、商业视点策略、镜头商业功能、蒙太奇关系、时长控制、注意力窗口规则）见 `skills/raw_prompts/storyboard_director.source.md`，本文件只定义输入、输出与边界。

## 输入（无需任何配置文件）

- `outputs/story.md`：已确认的广告剧本（由环节1产出），含广告总时长、核心卖点、目标受众、投放平台
- `outputs/style_bible.md`：已确认的视觉圣经（由环节3产出），含整体色调、光线风格、产品视觉要求、品牌调性规则

## 输出

写入 `outputs/storyboard.json`，并校验通过 `schemas/storyboard.schema.json`。

每个 shot 只包含 7 个字段：`shot_id`（`S###`）、`scene_id`（`SC###`，导演创建）、`duration_seconds`（>0 且 <=10）、`framing`（景别）、`camera_move`（运镜）、`action_desc`（可见可拍可执行的动作描述）、`advertising_text`（广告文字数组，无文字时为空）。

工作要求：
- 按广告注意力曲线拆镜头，强制覆盖黄金3秒钩子、痛点建立、卖点演示、产品英雄镜头（Money Shot）、品牌露出、CTA 全链路。
- 所有镜头总时长严格匹配广告要求时长，误差不超过 0.5 秒。
- 每个镜头有明确商业功能，相邻镜头有认知递进关系。
- 不编造产品 claim、价格、销量、评价、稀缺信息。

## 边界

- 不做资产拆分（人物/场景/道具清单）——那是 `plan-ad-assets` 的职责
- 不写图片提示词、视频提示词
- 不设计无商业价值的艺术化空镜头
- 不输出卖点分析、营销说明、创意解释类文字
- 不改广告脚本内容、产品卖点、品牌主张

## 质量门

- 每个镜头有明确商业功能（钩子/痛点/卖点演示/效果对比/产品英雄/品牌强化/CTA/节奏调节/信息补充）。
- 前3秒有强钩子镜头，每3-7秒有信息变化，无空镜。
- 有清晰的产品英雄镜头（Money Shot），产品清晰无遮挡、质感突出。
- 品牌 logo/slogan 清晰露出，停留至少 1.5 秒。
- 核心卖点通过镜头直观展示，不需额外解释。
- 所有镜头总时长匹配广告要求时长，误差 <=0.5 秒。
- 无 shot 超过 10 秒，shot_id 从 S001 连续编号，scene_id 规则正确。
- storyboard.json 通过 schema 校验，不含资产/提示词/解释类字段。

## V8 文字与时长契约

- 每个 shot 必须包含 `advertising_text`；没有广告文字时写空数组。
- 品牌名、Slogan、卖点、价格、促销、CTA、法律文字和包装必现文字，必须绑定到具体 shot，并写明精确内容、位置和呈现方式。
- 禁止把已声明广告文字推迟到后期补字；含文字镜头优先使用稳定构图和低运动幅度。
- 原子 shot 仍允许大于 0 且不超过 10 秒；后续 `plan-video-segments` 将其组合成 4–30 秒的 `V###`。
