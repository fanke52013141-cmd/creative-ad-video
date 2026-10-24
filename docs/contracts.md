# Video Flow 0.1 任务契约

新流程使用 `video_flow/contracts.py` 为可执行契约，旧 schemas/*.json 属 V8，不能互换。

初始 brief 要求 title、goal、narrative_form、distribution、duration_seconds、episode_count、production_mode、style、constraints、facts。事实条目有 claim/source。虚构项目明确标记；缺事实时不得虚构品牌功效。

候选：`{task_id,type,items}`。每项 id 唯一非空。具体必填字段见 contracts.py/FIELDS。
story：scene_goal/action/duration_seconds。
style：axis/rule/story_reason。
storyboard：scene_id/beat/action/start_state/end_state/duration_seconds/axis/cut_motivation/sound。
assets：kind/description/shot_ids/continuity_rules。
edit_sound：shot_id/picture_cut/sound/motivation。
字段类型：除 shot_ids 为非空字符串数组、duration_seconds 为正数外，其余必填字段均为非空字符串；结构化账本放附加字段，不占必填位。
可附加 dialogue、visual_notes、风险与替代方案等专业字段。时长合计与 brief 差不超过0.5秒。资产/声画必须覆盖全部镜头标识，不允许引用未知镜头。

媒体项（仅 `--media` run）：`init --media` 后新增 asset_media/board_media 扇出阶段。一次 dispatch 只取一个 item：`python -m video_flow dispatch RUN STAGE ITEM`（待办项见 status 的 items_pending）。任务包只含该项的切片内容与全局约束，`fanout` 字段给出 item、像素 size、target_file 与 provider profile。工作者产一张图到 target_file，candidate 为 `{task_id,type:"media_item",item,file,sha256,prompt}`，sha256 须为图片实际字节哈希；一任务一图，禁止合并。全部 item 完成后引擎汇总为 media 清单产物并照常走独立 review；revise 只重开被点名的 item（兄弟项结果保留），单项重生成也可用 `invalidate RUN STAGE --item ITEM`。
review：`{task_id,type:"review",target_sha256,coverage,verdict,issues,criteria}`。
coverage 必须无重复、精确覆盖目标 items.id。verdict 为 pass 或 revise。
issues：`{severity:"P0|P1|P2",location,reason}`；criteria：`{name,score:0..4,evidence}`。
pass 必须无P0/P1且每项评分至少3。证据要指向具体位置；机器仅验证格式与一致性，独立评审负责语义真实性。

评分锚点：0缺失/矛盾；1严重不足；2局部成立仍需修订；3成立且有具体证据；4在约束下清晰、有力、可执行。不得只给总分。

criteria.name必须无重复、精确等于packet.review_criteria中的英文标识；每项评分与证据独立，不允许自行挑简单指标替代必需指标。指标唯一来源为config/workflow.yaml。

receipt：`{task_id,agent_id,skill_sha256,input_hashes,output_sha256}`。input_hashes 与 packet 完全相同；output_sha256 是 candidate.json 实际字节 SHA256。协调器先 bind 真正子Agent ID，receipt 必须对应。ID是本地审计标签，尚非可信身份认证。

所有输出写 packet.output_root 下的 candidate.json 和 receipt.json。缺输入返回 needs_input，由主Agent记录 retry 的原因；不提交空产物冒充通过。修订后创建新任务，旧结果不可补交。原始 run/brief 不能直接改写；需求变更重新初始化一个run，或仅在已登记事实不变时 invalidate相应创作阶段。
