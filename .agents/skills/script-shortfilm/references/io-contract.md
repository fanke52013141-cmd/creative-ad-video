# 输入、候选与收据

本包遵从通用 story artifact，不建立只供短片使用的第二套流水线。`duration_seconds` 是秒数；不得以 `duration`、自然语言时长或字符串代替。根工作流和 `video_flow/contracts.py` 是运行时契约来源，本页只为专业字段提供额外含义。若运行时更新，主代理先解决版本差异再锁定任务，工作者不得自行改总标准。

## 必要输入

任务包至少给 task_id、目标、允许输出路径、Skill 版本与哈希、输入 revision/hash 和验收要求。brief 必须是对象，具备 title、goal、narrative_form、distribution、production_mode、style 六个非空字符串；duration_seconds 是正数；episode_count 是正整数；constraints 是字符串数组；facts 是对象数组，每项有 claim、source 非空字符串。constraints 和 facts 可以为空数组，表示提供者明确没有列出约束或事实；字段缺失不同于空数组，必须报缺口。

独立单部短片的 episode_count 通常为一，但不能在原始字段缺失时静默补一。若它大于一且涉及跨集悬念，主代理应重新判断路由，本包不把连载主写任务伪装成单部短片。distribution、production_mode、style 也不能因作者认为“不影响故事”而略去：展示环境会影响信息密度，制作方式会影响动作可实现性，风格会影响语气。词语过泛但可执行时声明解释继续；直接互相矛盾时报告具体冲突。

受众画像、角色数量、地点、对白政策、结尾开放度可放扩展字段或 constraints。它们一旦明确就是约束；未提供时不得编造年龄、职业和传播数据。虚构人物与事件属于创作设定，应与 facts 分开。遇到“基于真实事件”而没有可读事实源，先报事实材料缺失，不把原创例子写成真人经历。

## 候选输出

顶层必须有 task_id、type 为 story、非空 items。可以附 status 为 candidate、title、logline、theme_question、assumptions、source_refs、revision。每项必需 id、scene_goal、action、duration_seconds；本包另要求 dialogue 数组。id 在 revision 内唯一且稳定，删除后不把原 id 随意分配给另一段事件；新增场景可用新编号，并在修订说明给出前后映射。

scene_goal 写叙事功能，不只写人物愿望，例如“使观众得知她故意留下钥匙，并让对方第一次拥有离开的决定权”。action 用现在时写能看见或听见的连续事件，不能只有“展现孤独”。dialogue 每项有 speaker 和 text，可加 intention；没有对白填空数组，不能漏字段。对白中的事实必须来自 brief 或明确的虚构设定，不承担未核验的公共事实宣传。

可选 location、characters、state_before、state_after、choice、continuity、timing_note、omission_effect 提供给艺术指导、分镜和评审。choice 是关键选择场景的证据，不要求每次端杯子都伪造两难。所有 items 时长合计与 brief.duration_seconds 的绝对差须不超过零点五秒；通过这个检查只能说明数字符合，不证明实际表演可在该时长完成。

## 缺口输出

必要字段缺失时返回缺口报告，保留 task_id、type、status 为 needs_input、items 为空数组，并列 missing_inputs 的 field、reason、needed_from。它不满足可提交候选的非空 items 条件，必须停止在工作者回复，不调用 submit，不登记为已完成 story。若任务包本身没有 task_id，原样报告缺少 task_id，不伪造一个可混入运行登记的编号。

问题要可回答。例如“缺 brief.duration_seconds，无法判断事件容量；需要主代理提供秒数或已批准范围”，比“请补充更多细节”明确。不要用默认的九十秒示例掩盖缺失，不把主代理未回复当成同意。独立研究可继续整理已有材料，但不能越过缺口生成可被下游误用的完整候选。

## 工作收据与边界

随候选提供 task_id、agent_id、skill_sha256、input_hashes、output_sha256，准确记录引用的锁定内容。input_hashes 按任务包引用名映射到实际输入哈希，不填随意占位值；output_sha256 应从已落盘候选字节计算。若暂不能计算，报告未完成收据，不声称机械验证已通过。主代理最终提供的 receipt schema 优先于本页的最低约定。

另列 checks_executed 和 checks_pending，说明时长求和、必填字段、引用一致性等已执行项目；读演、分镜可拍性、独立创作评审若未发生就列待测。收据不能包含自授 accepted、用户签名或主代理审批。作者可以提交修复建议和自检证据，接纳权仍属于独立评审与主代理。

修订生成新 revision 与新哈希；附 change_summary 和 affected_item_ids。不得修改旧候选字节使已有评审哈希仍看似有效。输出落在任务包授权目录，本 Skill 包目录只存方法与合成评测材料，真实 run 的人物信息、事实文件与成品不要写入本包。
