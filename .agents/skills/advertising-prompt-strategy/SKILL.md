---
name: advertising-prompt-strategy
description: Build advertising-focused storyboard-image prompts from shared storyboard shots, approved style direction, mapped assets, and available product/brand references. Use when generating ad keyframes or storyboard reference images that must preserve product identity, packaging, logo, claims, CTA safe areas, and the selected standard or AI-native expression. Do not change the advertising strategy, storyboard, or asset registry.
---

# Advertising storyboard prompt strategy

## Inputs

- `outputs/storyboard.json`, `outputs/style_bible.md`, and `outputs/shot_asset_map.json`.
- Approved asset images and prior storyboard reference when allowed by the shared continuity policy.
- `config/verticals/advertising.yaml`.

## Output

For each `S###`, write the prompt file expected by the stable storyboard prompt stage, and aggregate it into `outputs/storyboard_prompts.md`. Preserve `recommended_frame_role` and `uses_previous_storyboard_reference` fields required by the existing validator.

## Procedure

1. Read only the current shot plus the minimum references required for continuity.
2. Preserve the shot's advertising function, approved claim, expression mode, action, framing, and camera intent.
3. Put product identity, geometry, material, packaging front, logo constraints, and approved brand colors before decorative style language.
4. Use references explicitly: product reference for identity, scene reference for environment, character reference for identity, and previous storyboard only as a same-scene placement anchor.
5. For AI-native shots, describe one controllable visual idea rather than stacking unrelated spectacle. For trust-critical shots, favor natural materials, credible behavior, restrained effects, and realistic optics.
6. Keep generated text minimal. When packaging copy, price, disclaimer, or CTA must be exact, reserve a clean post-production area and state that exact typography is composited later unless the selected tool supports reliable text rendering.
7. Add negative constraints for product deformation, false logo, misspelled packaging, duplicate objects, extra fingers, inconsistent materials, unreadable claim text, watermark, and unintended competitor cues.
8. Validate asset names, reference paths, frame role, prior-shot reference scope, and prompt coverage.

## Quality gate

- Prompt does not invent new products, claims, logos, offers, or assets.
- Product and brand fidelity outrank decorative spectacle.
- Exact text is routed to post-production when generation reliability is insufficient.
- Previous-shot reference is same-scene and placement-only.
- Every shot preserves its approved standard/AI-native decision and associated trust risk.
- Existing storyboard prompt validation passes.

## Failure handling

If a required product packshot, brand logo, or blocking asset is missing/unapproved, stop that shot and record the missing reference. Do not compensate by hallucinating the product appearance.

