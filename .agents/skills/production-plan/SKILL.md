---
name: production-plan
description: 为Video Flow v0.2把已审分镜转为平台生成片段、时间区间和最多四格的板清单；不调用视频生成。
metadata:
  version: "0.2.0-draft"
---

# 制作计划

读取任务包、锁定的 production 配置和 docs/contracts-v02.md。只写 output_root 的 candidate.json 与 receipt.json。使用包内原始分镜和资产，不改故事。

调用 video_flow.production_plan.build_production_plan 获得可检查提案。按目标平台模式容量分段，同场相邻镜优先组合；长镜只在已知动作边界拆段，短孤立镜需要明确稳定保持区间。计划必须保留每个源镜头毫秒范围，无遗漏、无重叠、不变速。没有适当动作边界时返回 needs_input。

核对每段 continuity_in/out、asset reference_keys、声音承接和板格关键瞬间。每板最多取配置允许格数，板格有 panel_id、源span与时刻，阅读顺序明确；多格板不是默认首帧。使用 actual reference_key，不凭空创建图片或音频标签。

输出 type=production_plan，schema_version=0.2.0，含 segments、boards；items 必须与 segments 内容一致且 id=video_id。交独立评审。receipt 按原任务哈希与真实 agent_id 写入，禁止自审或更新checkpoint。

正常例：12个2秒镜头，同场每3镜形成6秒片段。边界：一段5镜分4+1两板。失败：长镜没有动作拆点，不可删掉中间动作硬塞容量。验收以结构校验和独立评审为准。本包是功能草案，专业深度与真实行为评估尚未完成。
