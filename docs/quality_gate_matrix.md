# Quality Gate Matrix

| 阶段 | 必须通过的门槛 | 阻塞等级 |
|---|---|---|
| Idea Brief | 核心想法、时长、类型、限制不为空 | P0 |
| Story | 剧本可读、人物动机清楚、适合 2-5 分钟；不得输出 `story.json` | P0 |
| Art Direction | 用户视觉方向优先；无明确方向时先给候选方案；最终 `style_bible.md` 只含画面风格、整体色调、光线风格、AI 视觉执行要求 | P1 |
| Storyboard | 每个 shot 有时长、动作、具体构图/景别/镜头；不得定义资产 | P0 |
| Asset Manifest | 人物只按持续可见变化拆变体且名称不加“状态”；场景不按普通光影拆；道具只保留核心剧情道具；映射资产全部存在 | P0 |
| Character Assets | 输入为 `story.md + style_bible.md + asset_type + asset_name + output_prompt_path`；一个人物状态资产输出一份 21:9 人物资产图提示词 | P1 / final P0 |
| Scene Assets | 输入为 `story.md + style_bible.md + asset_type + asset_name + output_prompt_path`；核心空间结构明确；普通时间、光线、天气变化不拆新场景 | P1 |
| Prop Assets | 只为剧情关键、反复出现、需要特写、复杂或状态变化道具独立生成；普通道具正文控制 | P1 |
| Asset Image Generation | 可用即梦、ChatGPT、Codex 或外部工具；每个 asset_image_task 只生成一张图片文件；人物资产图允许 21:9 多视角单图 | P0 |
| Storyboard Prompts | 每个 shot 都有分镜图提示词；`frame_role` 必须与视频段计划一致；必须判断上一分镜引用；不得跨 `scene_id` 引用 | P0 |
| Storyboard Image Generation | 每个 `S###` 生成一张分镜参考图；需要站位连续时可引用上一分镜图作为 placement anchor | P0 |
| Video Prompts | `video_prompts.md/json` 齐全，中文-only，无默认 `@PROP`；可合并同 scene 连续 shots；合并总时长 `<= {max_generated_clip_seconds}s`；每条 `V###` 必须有 `merge_decision` 和 `frame_references` | P0 |
| Final Handoff | 只交付 story、video prompts、角色资产、场景资产和分镜图 | P0 |
