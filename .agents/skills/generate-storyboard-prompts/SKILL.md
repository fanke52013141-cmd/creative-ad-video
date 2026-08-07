---
name: generate-storyboard-prompts
description: Build deterministic V/SB/S packets and generate one storyboard-board prompt for each declared board.
---

# Generate Storyboard Prompts

Run `python scripts/build_storyboard_packets.py RUN_DIR`, then read each `outputs/storyboard_board_inputs/SB###.json` packet and write the corresponding `outputs/storyboard_boards/SB###.md` prompt using `skills/raw_prompts/storyboard_prompt_generator.source.md`.

**逐板隔离（强制）**：必须逐个读取单个 `SB###.json` packet，逐个写出对应的单个 `SB###.md` 提示词。禁止把多个 packet 合并处理，禁止在一条提示词里描述多个 `SB###` 板。每条 `SB###.md` 只描述自己那一个板（板内 ≤ 4 个分镜的拼接长图是允许的，跨板合并禁止）。下游 `fulfill-image-generation` 会据此逐板生成、一板一图。

Treat the board as the final visual source for scene, composition, set dressing, static effects and declared advertising text. Every `required_text` item must appear literally in the prompt with its declared placement and presentation. If `required_text` is empty, forbid all text; otherwise forbid only undeclared text, captions and watermarks.

Run the packet builder again to record final prompt hashes. Do not write image paths, hashes or approval state into `storyboard_board_manifest.json`.
