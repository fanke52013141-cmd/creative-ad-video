---
name: generate-asset-prompts
description: Generate exactly one prompt for each asset that requires generation and build the immutable prompt manifest.
---

# Generate Asset Prompts

Read the approved story, style bible and `asset_manifest.json`. Generate only the prompt paths declared by each `generation_required=true` asset. Use the character, scene and prop source prompts under `skills/raw_prompts/` as references.

After all prompt files exist, run:

```text
python scripts/build_asset_prompt_manifest.py RUN_DIR
```

Output only `outputs/asset_prompt_manifest.json` plus its declared prompt files. Do not modify the asset plan.
