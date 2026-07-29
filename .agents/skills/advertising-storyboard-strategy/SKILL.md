---
name: advertising-storyboard-strategy
description: Convert an approved advertising narrative and style bible into the shared shot-level storyboard JSON with clear advertising functions, timing, product/brand/claim/CTA sequencing, and generatable actions. Use for brand, product, performance, ecommerce, social, app-install, lead-generation, and promotional ad storyboards. Do not generate images, asset prompts, or final video prompts.
---

# Advertising storyboard strategy

## Inputs

- Approved `outputs/story.md` and `outputs/style_bible.md`.
- `config/verticals/advertising.yaml`.
- User-provided product and brand references.

Read `references/advertising-shot-planning.md` before selecting structure, timing, and shot functions.

## Output contract

Write only `outputs/storyboard.json` as the machine output and validate it against `schemas/storyboard.schema.json`.

Each shot must contain the shared fields `shot_id`, `scene_id`, `duration_seconds`, `framing`, `camera_move`, and `action_desc`. Encode advertising purpose, product/brand presence, dialogue/voiceover, on-screen text, music/SFX, persuasion note, and AI-leverage decision as labeled clauses inside `action_desc` until the shared storyboard schema is deliberately extended.

Do not output the user's table-based and paragraph-based formats as competing canonical artifacts. A human-readable preview may be derived from JSON, but JSON remains the source of truth.

## Procedure

1. Identify advertising type, objective, audience, primary message, purchase resistance, evidence, CTA, duration, platform, aspect ratio, and reference status.
2. Select the simplest structure that supports the objective: Hook–Body–CTA, Problem–Solution–Benefit, Before–After, Demonstration, Testimonial, Promotion, or Emotional Scene.
3. Allocate timing from the vertical profile. Ensure shot durations sum to the selected total duration and each shot is no longer than the shared maximum.
4. Assign exactly one primary advertising function to each shot: hook, pain/context, product reveal, mechanism/demo, proof, benefit/result, offer, brand memory, or CTA.
5. Decide the product, brand, claim, evidence, and CTA appearance sequence. Do not place a logo-only opening where the selected strategy requires a hook.
6. For every shot, choose standard or AI-native expression using the trust-versus-leverage rules in the reference. Do not force AI spectacle into testimony, UGC, expert proof, precise packaging, or delicate human emotion.
7. Write objective, observable, generatable actions. Do not invent claims, prices, sales figures, reviews, scarcity, certifications, or guarantees.
8. Run sequence, duration, message coverage, and schema checks before handoff to the stable asset registry.

## Quality gate

- Every shot has a primary advertising function.
- Product, primary message, evidence, brand and CTA appear at intentional times.
- All shot durations add up exactly to the selected duration.
- `action_desc` distinguishes spoken audio from visual text and contains only supplied/approved claims.
- AI-native choices have a meaningful leverage reason; realistic choices have a trust reason.
- Output validates against `schemas/storyboard.schema.json` and the existing project validator.

## Failure handling

If product, objective, audience, duration, primary message, or CTA is missing, stop and ask up to three questions. If only style references are missing, continue from the approved style bible and record `reference_status: not_provided` in the human review note.

