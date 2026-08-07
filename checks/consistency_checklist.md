# V8 Consistency Checklist

## Pipeline

- [ ] `config/pipeline.yaml` 通过 PipelineSpec Schema。
- [ ] 11 个阶段全部声明至少一个可追踪输出。
- [ ] checkpoint 阶段结构由 PipelineSpec 生成，模板不复制阶段列表。
- [ ] 每个 `codex_skill` 都存在于 `.agents/skills/<name>/SKILL.md`，frontmatter name 完全一致。

## Immutable data

- [ ] `asset_manifest.json` 不含媒体路径、哈希、版本或审批状态。
- [ ] `storyboard_board_manifest.json` 不含图片路径、哈希或审批状态。
- [ ] 资产媒体只写入 `asset_media_manifest.json`。
- [ ] 分镜板媒体只写入 `storyboard_media_manifest.json`。
- [ ] 每条 Media Manifest 记录引用真实 Artifact Revision。
- [ ] 每条 Approval 引用真实 Artifact Revision 且哈希一致。

## Mapping and delivery

- [ ] 每个 S### 被一个 SB### 覆盖，每个 SB### 属于一个 V###。
- [ ] `video_prompt_manifest.json` 是唯一视频提示词索引，不存在 `video_prompts.json`。
- [ ] 每个 `V###` 时长在 4–30 秒，短段不通过虚构停顿补齐。
- [ ] 项目未指定画幅时使用 `16:9`，Manifest、提示词和最终包一致。
- [ ] 视频参考只包含 Board、Character 和 `advertised_product`；不存在 Scene、普通 Prop、装饰或特效引用。
- [ ] 每个 Prop 都有 `business_role`，`product_assets` 只包含 `advertised_product`。
- [ ] 每条广告文字绑定到具体 Shot、进入 Board Prompt，并通过逐字/无额外文字审批。
- [ ] 文档和提示词不存在后期补字回退。
- [ ] 打包器不通过文件名或目录顺序猜测关系。
- [ ] Production 拒绝未批准或审批后修改的媒体。
- [ ] Delivery 校验最终包内每个文件的大小和 SHA-256。

## Tests and repository

- [ ] 契约、单元、完整 Production/Delivery 测试全部通过。
- [ ] Markdown 不引用不存在的文件。
- [ ] 不提交真实客户内容、媒体、local_runs、密钥或本地账号信息。
