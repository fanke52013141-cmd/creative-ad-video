---
name: generate-media
description: 当任务包为单个 fanout 媒体项（media_item）时，为该项独立生成一张参考图；一任务一图，禁止合并，输出候选与回执。
metadata:
  version: "0.1.0"
---

# 单项媒体生成协议

你收到的任务包 `artifact_type` 为 `media_item`：包内 `fanout` 字段给出唯一一个生成项（`item`、`kind`、`size`、`target_file`、`profile`），`inputs` 给出该项的独有内容（资产描述或一块分镜板的镜头列表）与全局约束（brief、style）。你只为这一个项工作。

## 执行步骤

1. 只读任务包、任务契约与锁定技能；不读取 run 内其他产物。
2. 从该项独有信息派生中文图像提示词：写实基调服从 style 的光线/色彩/材质约束；`kind: character` 出人物参考（含固定外观特征），`kind: space` 出空间定场（按项内状态说明），`kind: board` 以该板镜头列表的关键状态（优先首镜 start_state 或板内核心动作的可见结果）为画面目标，画面必须落在该板时空内，不得拼入其他板的道具状态。
3. 调用宿主图像工具（协调器在派发消息中告知调用方式；当前为 toapis-image-gen 的 `gen_image.py`），参数：`--model` 与 `--quality` 取 `fanout.profile`，`--size` 取 `fanout.size`（像素宽x高），`--out` 为 `fanout.target_file`（run 内相对路径，写到任务包给定的绝对位置）。工具不可用或连续失败两次：不写候选，报告 needs_input。
4. 校验产物：文件存在、字节数大于 0，计算其 SHA256。
5. 写 `output_root/candidate.json`：`{"task_id": "<任务包task_id>", "type": "media_item", "item": "<fanout.item>", "file": "<fanout.target_file>", "sha256": "<图片实际字节SHA256>", "prompt": "<你发出的完整提示词>", "model": "<实际模型名>", "quality": "<实际质量档>"}`。
6. 等协调器绑定 agent ID 后写 receipt.json（task_id、agent_id、skill_sha256、input_hashes 逐字抄任务包、output_sha256 为 candidate.json 字节哈希）。

## 硬规则

- 一任务一图：禁止在一张图里合并多个 item、多个资产或多个板；禁止批量调用。
- 只写三个文件：目标图片、candidate.json、receipt.json；不得改动 run 其他内容。
- 修订轮（任务包含 repair_feedback）：只针对被点名的 item，按意见调整提示词后重新生成同一路径；不重生成未被点名的项。
- 诚实报告：生成失败、参数被拒、文件校验不过，如实说明，不提交空候选。
