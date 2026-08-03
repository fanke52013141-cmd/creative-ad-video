# Quality Gate Matrix

| 阶段 | 必须通过的门槛 | 阻塞等级 |
|---|---|---|
| Idea Brief | 核心想法、时长、类型、限制不为空 | P0 |
| Story | 剧本可读、人物动机清楚、总时长匹配项目广告时长；不得输出 `story.json` | P0 |
| Creative Review（idea_generation 审批前） | 运行 `advertising-idea-review`：提取世界规则、八维审查、输出分级意见并写 `outputs/idea_review_feedback.md`。审查只出意见不放行；修订后不自动重审，二次审查由人工触发 | P1（建议） |
| Art Direction | 用户视觉方向优先；无明确方向时先给候选方案；最终 `style_bible.md` 只含画面风格、整体色调、光线风格、AI 视觉执行要求 | P1 |
| Storyboard | 每个 shot 有时长、动作、构图/景别/镜头及 `advertising_text`；广告文字不得后补；不得定义资产 | P0 |
| Asset Manifest | 人物只按持续可见变化拆变体；场景不按普通光影拆；每个 Prop 声明 business_role；映射资产全部存在 | P0 |
| Character Assets | 输入为 `story.md + style_bible.md + asset_type + asset_name + output_prompt_path`；一个人物状态资产输出一份 21:9 人物资产图提示词 | P1 / final P0 |
| Scene Assets | 输入为 `story.md + style_bible.md + asset_type + asset_name + output_prompt_path`；核心空间结构明确；普通时间、光线、天气变化不拆新场景 | P1 |
| Prop Assets | 广告商品必须独立生成；普通剧情道具和布景只进入分镜板，不作为视频参考 | P1 |
| Asset Image Generation | 可用即梦、ChatGPT、Codex 或外部工具；每个 asset_image_task 只生成一张图片文件；人物资产图允许 21:9 多视角单图 | P0 |
| Storyboard Prompts | 每个 shot 被一个 Board 覆盖；frame role 与视频段一致；场景、装饰、静态特效和声明广告文字全部在 Board 中固定 | P0 |
| Storyboard Image Generation | 每个 `SB###` 生成一张分镜板长图；审批逐字核验声明文字并确认无额外文字 | P0 |
| Video Prompts | 每个 `V###` 为 4–30 秒，显式声明画幅（默认 16:9）；只引用 Board、Character、Product；文字约束按 Board 是否含广告文字切换 | P0 |
| Final Handoff | 按 Manifest 交付 video prompts、对应 Boards、人物和广告商品参考；不携带场景/装饰/普通道具参考 | P0 |
