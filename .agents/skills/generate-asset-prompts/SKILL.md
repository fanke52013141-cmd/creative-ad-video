---
name: generate-asset-prompts
description: Generate exactly one prompt for each asset that requires generation and build the immutable prompt manifest.
---

# Generate Asset Prompts

Read the approved story, style bible and `asset_manifest.json`. Generate only the prompt paths declared by each `generation_required=true` asset. Use the character, scene and prop source prompts under `skills/raw_prompts/` as references.

**逐资产隔离（强制）**：为每个 `generation_required=true` 的资产单独生成一条独立的提示词文件，一个资产一份 prompt。禁止把多个资产写进同一份提示词，禁止在一条提示词里要求生成多个资产。转面参考图内部的多视角（面部/正面/侧面/背面）属于单一资产的正常构图，允许；跨资产合并禁止。下游 `fulfill-image-generation` 会据此逐个资产生成、一资产一图。

After all prompt files exist, run:

```text
python scripts/build_asset_prompt_manifest.py RUN_DIR
```

Output only `outputs/asset_prompt_manifest.json` plus its declared prompt files. Do not modify the asset plan.
