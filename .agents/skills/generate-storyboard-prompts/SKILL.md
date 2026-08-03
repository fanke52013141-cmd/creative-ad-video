---
name: generate-storyboard-prompts
description: Build deterministic V/SB/S packets and generate one storyboard-board prompt for each declared board.
---

# Generate Storyboard Prompts

Run `python scripts/build_storyboard_packets.py RUN_DIR`, then read each `outputs/storyboard_board_inputs/SB###.json` packet and write the corresponding `outputs/storyboard_boards/SB###.md` prompt using `skills/raw_prompts/storyboard_prompt_generator.source.md`.

Treat the board as the final visual source for scene, composition, set dressing, static effects and declared advertising text. Every `required_text` item must appear literally in the prompt with its declared placement and presentation. If `required_text` is empty, forbid all text; otherwise forbid only undeclared text, captions and watermarks.

Run the packet builder again to record final prompt hashes. Do not write image paths, hashes or approval state into `storyboard_board_manifest.json`.
