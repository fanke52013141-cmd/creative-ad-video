---
name: fulfill-image-generation
description: Fulfill asset or storyboard image requests through a selected provider or manual import and register immutable media revisions.
---

# Fulfill Image Generation

For asset images, consume `asset_prompt_manifest.json`, use the queue scripts, register every result through `register_image_result.py`, and produce `asset_media_manifest.json`.

For storyboard images, consume `storyboard_board_manifest.json`, register every result through `register_storyboard_result.py`, and produce `storyboard_media_manifest.json`.

Never overwrite media, edit an upstream plan manifest or invent approval state. Approval is recorded only through `approve_media.py`.
