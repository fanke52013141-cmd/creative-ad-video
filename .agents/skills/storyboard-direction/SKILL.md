---
name: storyboard-direction
description: 将已锁定的剧本与艺术指导转译为可剪辑、可执行的通用分镜候选；设计节拍、空间调度、镜头动机、声画、连续性账本和生成风险。适用于广告、叙事短片、无对白片等前期分镜；不替代剧本定稿、独立审查或具体平台提示词。
metadata:
  version: "1.0.0"
  language: zh-CN
  status: draft
---

# 分镜导演

## 边界与交接

输入应含任务标识、目标、锁定剧本及版本化引用、艺术指导、时长与画幅、制作方式、不可变事实和验收约束。读取必要原文，不只读他人摘要。缺剧本、关键因果、产品事实或必需资产时返回 `needs_input`，列缺失字段及受影响镜头；非关键偏好可作显式假设。只交付前期文本候选，不生成付费媒体、不发布、不修改总检查点、不代替用户批准。

输出是通用 artifact：`task_id`、`type: "storyboard"`、`items`。每镜必须含 `id/scene_id/beat/action/start_state/end_state/duration_seconds/axis/cut_motivation/sound`，除正数时长外均为非空字符串，详见 [契约](schemas/storyboard-artifact.schema.json)。场景集合精确覆盖上游 story.items.id，总时长与 brief 差不超过零点五秒；平台片段限制只来自当前任务 profile。此契约不能直接冒充旧 V8 的 `shots` 格式。

## 执行顺序

1. **锁定边界**：列输入 revision/hash、原文范围、事实与假设；冲突交主代理裁决，不能靠镜头掩盖剧本缺口。
2. **标节拍**：把每段变成“观众先知道什么—人物做何选择—观众后知道什么”，分开动作与状态变化。按 [节拍方法](references/01-beat-and-information.md) 生成节拍到镜头映射。
3. **画空间**：给人物、道具、出入口和机位统一命名，锁轴线、视线、运动方向和遮挡。按 [空间与镜头](references/02-space-and-camera.md) 选可执行的调度。
4. **定镜头**：逐镜写起止状态和切换理由。景别、机位、运动必须服务信息、关系或感受；删除无贡献镜头，保留可剪接的动作接点。
5. **定声画**：先写声源、信息作用、声画关系，再写音乐气氛；用 [声画与连续性](references/03-sound-continuity-risk.md) 建账本及风险替代方案。
6. **走完整片**：按真实时长朗读动作、对白与停顿，检查前后镜头、总时长、画幅安全区、可见事实和上游约束；不把纸面估时当观众测试。
7. **交候选**：输出 artifact、必要的空间说明、账本、风险及作者收据。独立审查由其他角色完成；作者不得填写接受、通过或用户签名。

## 分支与失败处理

- 广告读取 [咖啡案例](references/04-coffee-case.md)：检查产品出现是否引发行动，不擅造功效或商业承诺。
- 无对白叙事读取 [无对白案例](references/05-silent-case.md)：保证选择、阻力、后果可由画面与声音辨认，不能用解释文案补救。
- 生成式制作在设计稳定后拆风险，不默认必须碎切；复杂接触、身份延续、精确文字优先安排参考、合成或剪辑方案。
- 已知约束互斥时返回 `blocked` 与最小改动选择；只缺材料时返回 `needs_input`，不输出假装完整的镜表。

## 验证与阅读

执行 `python scripts/validate_package.py --package-root <本包绝对路径>` 检查引用、契约、示例与实际汉字数。用 [评估](evaluation/README.md) 的锚点记录字段级证据；机械成功只能说明格式与计数，不能构成创作验收。外部资料的可访问范围、原意与本包转译见 [来源](references/06-evidence.md)。初次执行先读前三份方法；案例按形式选读；修复任务同时读 [坏例修复](references/07-repair-playbook.md)。
