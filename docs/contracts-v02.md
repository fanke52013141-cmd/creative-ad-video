# Video Flow 0.2 制作契约

通过 init 的 --production-config 显式启用，必须同时 --media。未启用时继续使用0.1契约，旧run不原地升级。执行规则仍由本项目AGENTS与锁定工作流决定。

生产配置分别选择图片来源和视频平台参数，所有值写进run/standard/production.json并锁定哈希。user_supplied表示依据用户手册，并未确认实际账号入口；test_only只用于合成测试。平台执行标签仍需要用户实际上传时核对。

正式Schema位于 video_flow/schemas/v02；源码模块 registry、production_plan、prompts、media 负责跨字段检查。候选必需schema_version=0.2.0。story/storyboard只用整数duration_ms。brief保留duration_seconds，精确转换为毫秒后核对；不可同时为同一镜维护两个时间来源。

## 资产

assets.items 每项含id、kind、description、display_name、continuity_rules、invariant_features数组、shot_ids、states和media_requirements。state含state_id、description、shot_ids；媒体需求含reference_key、state_id、view、required、coverage_policy。当前运行队列支持independent策略，scene_reference未实施，遇到时明确反馈。人物、空间、物品均按需求独立派发；没有人物或物品时清单注明不适用。

同一个reference_key表示身份/状态/视图，返修递增revision。图片必须放在任务指定路径，不覆盖已接受旧图。实际可解码PNG、尺寸与哈希符合任务才可提交，视觉审查仍需独立看图。

## 分镜与制作计划

storyboard.items 每镜有id、order、scene_id、beat、action、start_state、end_state、duration_ms、shot_size、camera_position、primary_camera_motion、axis、cut_motivation、lighting、sound、asset_bindings。binding含asset_id、state_id、purpose、start_state、end_state。

production_plan读取完整分镜、资产和声音，输出segments、boards及供review覆盖的items。items是segments逐项加id=video_id的精确镜像。可用production_plan.build_production_plan制作初稿；先根据asset_bindings将当前镜所需资产视图转为reference_keys，禁止省略人物/物品引用。

segment含video_id、order、mode、scene_id、source_spans、generation_duration_ms、timeline、padding、continuity_in/out、reference_keys。每个源镜区间精确覆盖，主时间轴无空档。board含board_id、video_id、kind、layout、reading_order、panels、reference_keys；每panel是明确span内的一个关键时刻，每板最多四格。

## 视频提示词

每个任务对应一个V片段，任务包fanout.spec.segment给出计划，fanout.references提供本段准确素材绑定。候选含type=video_prompt、item、video_id、mode、duration_ms、references（原样复制任务绑定）、global_setting、timeline、audio、constraints。

timeline逐项复制计划的local_start_ms/local_end_ms/span_id或padding_id，并增加action、camera、sound。正文引用使用 `{{ref:reference_key}}`，不手写@图片序号。程序渲染正式名称与计划上传标签。candidate不必包含prompt；若包含必须逐字等于渲染结果。

素材只锁定明确维度；一个主空间运动允许必要对焦变化。情绪在全局可简述，动作段提供可见证据。用户台词、字幕和音乐选择优先。多格板只作构图/镜序参考，不能当成单格首帧。

## 审查与诚实边界

review的criteria以packet为准，coverage精确列items。视觉评审必须实际查看所有目标图，记录证据；文件哈希和解码检查不证明外貌一致。作者与评审身份隔离，automatic仍独立评审。媒体验收、平台绑定和视频效果分别记录，交付不宣称视频已经生成。

当前基础专业包中production-plan与prop-visual-design为draft；深度知识包和真实创作行为测试的进度单独记录。合成端到端测试验证执行与交付，不代替真实创意质量。

## 任务包到候选的具体映射

逐片段工作者遵循下表，不沿用0.1逐镜字段：

| 候选字段 | 类型 | 唯一依据 |
| --- | --- | --- |
| task_id | string | packet.task_id |
| schema_version | string | 固定0.2.0，与packet一致 |
| type | string | video_prompt |
| item | string | packet.fanout.item，例如PROMPT-V001 |
| video_id | string | packet.fanout.spec.segment.video_id |
| mode | string | 同一segment.mode |
| duration_ms | 正整数 | 同一segment.generation_duration_ms |
| references | 数组 | packet.fanout.references原样复制，含reference_key、canonical_name、file、sha256、media_revision、planned_slot、role |
| global_setting | 非空中文 | brief/style与当前场景约束，正文引用用受控token |
| timeline | 有序数组 | 同一segment.timeline原样保留边界与span/padding身份，逐项增加action/camera/sound |
| audio | 非空中文 | edit_sound和用户需求；明确静音或后期制作也是合法值 |
| constraints | 非空中文 | 本段相关约束，不删除用户明确需求 |

timeline的local_start_ms和local_end_ms是本段相对整数毫秒；source_spans的source_start_ms/source_end_ms是源镜内部的范围。跨段承接由segment.continuity_in/out给定，可能是含state的对象；程序渲染其state。作者不能用全片秒数替代本段毫秒，不能把padding写成源剧本新事件。

例如任务确有reference_key为CHAR001.work.front时，可写 `{{ref:CHAR001.work.front}}抬起右手，手指停在门把前`。任意未知key、未解析token、作者自行写的@图片序号或改动references均应被拒绝。每段planned_slot从1重新分配，不复用上段编号。

普通交谈的自然语言提示词与0.1逐镜候选继续使用原契约；本表仅适用于明确启用的0.2任务。candidate.json中的prompt可省略；显式提供时必须等于程序渲染。receipt.output_sha256由作者计算实际候选文件字节，不手抄哈希，不把内部对象重新序列化后的哈希冒充文件哈希。

## 交付与独立校验的边界

导出读取已接受并经run审计的产物，生成剧本、详细分镜、分类图片、分镜板和每V对应TXT。包内只引用相对路径，规范名称等于图片文件名去扩展名。独立verify-package重读全部文件、重算hash、解码图片，并检查片段时间覆盖、板格顺序、素材映射及锁定的有限平台容量。

manifest与可重算的validation_report不进入payload哈希集合，避免自引用。源码产物审计与包内完整性是两项不同检查；无签名manifest的包内一致性不提供身份认证。导出器不能用自己写入的passed=true代替独立复验。

正式素材包写production_package_ready；mock或test_only来源写synthetic_package_ready，并说明图像只为协议测试。两者均保留平台绑定pending、外部视频结果unverified。图片视觉通过与视频实际效果通过也分别记录。

## 导入身份与宿主适配

宿主职责见[宿主接口契约](../adapters/host-contract.md)。人工提供已有图片可以通过明确的导入路径进入媒体处理，但必须保留来源、文件hash与独立审查。当前没有专用导入执行者时，不能伪造一个真实agent_id来绕过bind。后续import actor契约应与真正的worker身份分别登记，不能把字符串标签当成认证证明。

DeepSeek接入状态见[DeepSeek Harness适配说明](../adapters/deepseek-harness.md)。文档描述能力映射与待执行验收，不代表已在该宿主完成试跑。工具名称由实际环境发现，不从其他平台推断。
