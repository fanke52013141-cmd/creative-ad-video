---
name: plan-ad-assets
description: Convert an approved story and storyboard into stable character, scene and key-prop plans without generating media.
---

# Plan Ad Assets

Read `outputs/story.md`, `outputs/storyboard.json` and `outputs/style_bible.md`. Produce only `outputs/asset_manifest.json` and `outputs/shot_asset_map.json`, conforming to their schemas.

Use `references/asset-rules.md`. Do not write media paths, hashes, revisions or approval state into the asset plan. Complete the stage only after both manifests cover every storyboard shot.

Every prop must declare `business_role` as `advertised_product`, `story_prop` or `set_dressing`. Only the advertised product is eligible for an independent video-model reference; an advertised product must set `generation_required=true`. Ordinary props and set dressing are resolved into storyboard boards and must not become video references.
