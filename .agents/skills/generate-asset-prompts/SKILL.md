---
name: generate-asset-prompts
description: Generate exactly one prompt per asset that requires generation and build the immutable prompt manifest. In single mode (default) each asset gets exactly one pure-text prompt matching its declared reference layout; advertised products get a master-image handling instruction instead of an AI generation prompt.
---

# Generate Asset Prompts

Read the approved story, style bible and `asset_manifest.json`. Generate only the prompt paths declared by each `generation_required=true` asset. Use the character, scene and prop source prompts under `skills/raw_prompts/` as references.

**逐资产隔离（强制）**：为每个 `generation_required=true` 的资产单独生成一条独立的提示词文件，一个资产一份 prompt。禁止把多个资产写进同一份提示词，禁止在一条提示词里要求生成多个资产。转面参考图内部的多视角（面部/正面/侧面/背面）属于单一资产的正常构图，允许；跨资产合并禁止。下游 `fulfill-image-generation` 会据此逐个资产生成、一资产一图。

**单份化（强制）**：按 `asset_manifest.json` 中每个资产的 `reference_layout` 只生成对应的一份提示词（`prompt_mode` 缺省为 `single`；显式声明 `full` 时才保留旧的双份输出）：

- `character_turnaround_21x9_v1`（characters）→ 只生成角色转面参考图提示词（21:9 四视图），不生成单人立绘。
- `scene_keyplate_quad_v1`（scenes）→ 只生成 2×2 四宫格提示词（16:9），不生成 Key Plate 单视图。
- `prop_single_reference_v1`（props）→ 只生成单参考图提示词（16:9）。

**纯文本（强制）**：提示词文件只包含提示词正文本身。禁止写入标题、来源说明、分段标记、代码围栏（`##`、`>`、``` ```text ``` 等）。资产名称、画幅、作用等元信息由 manifest 字段承载（`asset_id`、`reference_layout`、`prompt_scope`、`output_prompt_path`），不得写进提示词文件。

**广告商品分支（强制）**：`business_role=advertised_product` 的资产不参与 AI 文生图。其提示词文件固定为「商品母版处理指令」：引用用户上传的真实商品图（`references/` 下约定路径）、禁止 AI 重绘包装与包装文字、场景合成只允许透视/光照/阴影/景深/位置匹配。提示词文件同样只含指令正文，无多余标记。

After all prompt files exist, run:

```text
python scripts/build_asset_prompt_manifest.py RUN_DIR
```

Output only `outputs/asset_prompt_manifest.json` plus its declared prompt files. Do not modify the asset plan.
