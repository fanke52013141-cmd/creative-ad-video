---
name: fulfill-image-generation
description: Fulfill asset or storyboard image requests through a selected provider or manual import and register immutable media revisions.
---

# Fulfill Image Generation

For asset images, consume `asset_prompt_manifest.json`, use the queue scripts, register every result through `register_media_result.py --kind asset`, and produce `asset_media_manifest.json`.

For storyboard images, consume `storyboard_board_manifest.json`, register every result through `register_media_result.py --kind storyboard`, and produce `storyboard_media_manifest.json`.

Never overwrite media, edit an upstream plan manifest or invent approval state. Approval is recorded only through `approve_media.py`.

## 单任务生成协议（强制）

生成图片必须走"队列逐个取任务 → 一个任务一张图 → 立即登记 → 再取下一个"的循环，**禁止**一次性读取整份 manifest 后批量生成。

资产图循环：

```text
# 前置（只需一次）：由 asset_prompt_manifest.json 生成逐任务队列 image_generation_queue.json
python scripts/build_image_queue.py RUN_DIR

loop:
  1. python scripts/execute_image_queue.py RUN_DIR --provider codex_builtin
     # 该脚本一次只返回恰好一个 IMG-#### 任务及其 prompt_path
  2. 只打开返回任务的 prompt_path 作为唯一输入，调用图像工具生成 1 张图
  3. python scripts/register_image_result.py RUN_DIR <task_id> --source-file <生成的单张文件>
  4. 回到步骤 1，直到脚本输出 "No eligible image tasks"
```

分镜板图循环：

```text
loop:
  1. python scripts/execute_storyboard_image_queue.py RUN_DIR --provider codex_builtin
     # 该脚本一次只返回恰好一个 SB### 板及其 prompt_path
  2. 只打开返回板的 prompt_path 作为唯一输入，调用图像工具生成 1 张图
  3. python scripts/register_media_result.py RUN_DIR --kind storyboard --id <board_id> --source-file <生成的单张文件>
  4. 回到步骤 1，直到脚本输出 "No eligible board tasks"
```

## 硬规则：禁止合并生成

- 每次图像调用的输入 = 恰好一个 `IMG-####` 或一个 `SB###` 的 `prompt_path`，绝不把上级 manifest 或多个任务的提示词拼在一起喂给模型。
- 禁止把多个资产合并到一张图；禁止把多个分镜板（多个 `SB###`）合并到一张图。
- 每次调用只产出 1 张图片，登记时一个 `task_id` / `board_id` 只对应一个源文件。

## 允许的板内 / 图内多画面（不属于合并）

以下是设计本身，不违反上述硬规则，不得误判为"多图挤一张"：

- 单个 `SB###` 分镜板内部是一张含 ≤ 4 个分镜的拼接长图。
- 角色资产的转面参考图内部含面部特写 + 正面 + 侧面 + 背面等多视角。

判定标准：一张图只能承载"同一个 `SB###` 板"或"同一个资产"的内容；跨板、跨资产即为违规合并。
