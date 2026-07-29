---
name: advertising-quality-gate
description: Review a completed advertising-video production package for message coverage, claim evidence, product and brand consistency, CTA, platform duration, required assets, and unresolved generation issues. Use before final advertising handoff; do not rewrite upstream artifacts unless the user asks for fixes.
---

# Advertising quality gate

## Inputs

- `outputs/story.md`, `style_bible.md`, `storyboard.json`.
- Asset, image-result, storyboard, and video-prompt manifests available in the run.
- `config/verticals/advertising.yaml`.

## Output

Write `outputs/vertical_review.json` conforming to `schemas/vertical_review.schema.json`.

## Procedure

1. Trace the primary message, product mechanism, evidence, benefit, offer, and CTA from story.md through storyboard, assets, and final video prompts.
2. Check every claim. Mark unsupported or materially altered claims as blocking.
3. Confirm required asset roles exist and approved canonical references are used.
4. Check product appearance, packaging, logo, brand colors, and end card instructions for contradictions.
5. Check duration, aspect ratio, hook timing, CTA, and mandatory disclaimer status against the vertical profile.
6. Classify every issue as `blocking`, `warning`, or `note`; name the upstream stage that owns the fix.
7. Set overall status to `approved` only when no blocking issue remains.

## Verification

- Every configured quality gate has one result.
- Every blocking issue names `fix_stage` and affected artifact.
- Unknown mandatory disclaimer rules prevent `approved` status.
- JSON validates against `schemas/vertical_review.schema.json`.

