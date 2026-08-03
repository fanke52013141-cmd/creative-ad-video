# V8 Video Prompt Generation Protocol

当前流程按 `V###` 输出 `outputs/video_prompts/V###.md`，并由 `video_prompt_manifest.json` 建立显式关系。

## 输入边界

必需结构输入：

```json
{
  "video_segment_plan": "./outputs/video_segment_plan.json",
  "storyboard_board_manifest": "./outputs/storyboard_board_manifest.json",
  "storyboard_media_manifest": "./outputs/storyboard_media_manifest.json",
  "asset_manifest": "./outputs/asset_manifest.json",
  "asset_media_manifest": "./outputs/asset_media_manifest.json",
  "checkpoint": "./checkpoint.json"
}
```

视频模型实际图片参考只允许分镜板、人物和广告商品。场景、装饰、特效、风格图和普通道具不进入素材区或最终生产包。

## 时长与画幅

- 每个 `V###` 必须为 4–30 秒。
- 时长等于其 `source_shots` 时长之和，不允许填充假停顿。
- 使用 `checkpoint.ad_production.aspect_ratio`。
- 未设置或为空时使用 PipelineSpec 默认值 `16:9`。
- 提示词和 `video_prompt_manifest.json` 都必须显式记录实际画幅。

## 输出格式

```markdown
素材：
@SB001_分镜板图
@人物资产名
@商品资产名

画幅比例：16:9

提示词：
以分镜板锁定场景、构图、装饰、静态特效和广告文字，只描述人物/商品动作、镜头、节奏和声音。

约束：
……
```

## 允许描述的内容

- 人物动作、表情和姿态变化。
- 商品展示、开合、旋转和人物交互。
- 单一镜头运动和镜头衔接。
- 时间、节奏、台词、环境音和配乐。
- 分镜板中已经出现的雨、烟、粒子等元素如何运动。

## 禁止内容

- 重新描述或引用场景资产。
- 重新设计装饰、静态特效、光影和构图。
- 引用普通剧情道具或布景资产。
- 新增分镜板没有的广告文字。
- 使用后期叠加或后期替换文字作为回退。

## 文字约束

无声明广告文字：

```text
无字幕、无 Logo、无水印。
```

有声明广告文字：

```text
保持分镜板中已经出现的广告文字内容、位置和样式不变；禁止新增文字、乱码、变形、漂移和水印。
```

## 自检

- `video_prompt_manifest.schema_version` 为 `2.0`。
- 每个记录都有 `duration_seconds`、`aspect_ratio`、`character_assets` 和 `product_assets`。
- 不存在 `scene_assets` 或 `prop_assets`。
- 视频提示词中的 `@名称` 均属于白名单。
- 默认画幅为 `16:9`，自定义画幅贯穿分镜、提示词和打包结果。
