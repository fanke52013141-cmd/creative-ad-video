---
name: generate-video-prompts
description: Generate one Chinese video prompt per video segment from explicit board and approved media relationships.
---

# Generate Video Prompts

Read `video_segment_plan.json` and `storyboard_board_manifest.json`. When media stages were fulfilled, consume only approved storyboard boards, character assets and assets whose `business_role` is `advertised_product`; a configured draft-only skip may omit media references. Never reference scenes, set dressing, effects, style boards or non-product props. Write `outputs/video_prompts/V###.md` using `skills/raw_prompts/seedance_video_prompt.source.md`.

Use the project aspect ratio from `checkpoint.json`; when it is absent, use the PipelineSpec default `16:9`, and state the ratio explicitly in every prompt. Treat scene, composition, decoration, static effects and advertising text as locked by the storyboard board. Describe only motion, performance, camera, timing and sound. If the board declares advertising text, require it to remain unchanged and forbid new text; never suggest post-production replacement.

After all prompts exist, run:

```text
python scripts/build_video_prompt_manifest.py RUN_DIR
```

Do not create `video_prompts.json` or infer relationships from filenames.
