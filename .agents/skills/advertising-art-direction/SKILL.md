---
name: advertising-art-direction
description: Translate an approved advertising narrative, brand assets, product facts, audience, platform, and references into an executable commercial visual direction and shared style bible. Use for commercial art direction, brand visual strategy, product-ad look development, color and lighting systems, product hero rules, moodboard grammar, platform adaptation, and AI visual consistency. Do not write the ad narrative, storyboard shots, asset list, or final generation prompts.
---

# Advertising art direction

## Position in the pipeline

Run after `advertising-content-strategy` is approved and before `advertising-storyboard-strategy`. Decide what the advertisement should look like and why. Do not decide shot-by-shot action or camera scheduling.

## Inputs

- Approved `outputs/story.md`.
- Brand guide, product/packaging reference images, required logos, fonts, colors, claims and restrictions supplied by the user.
- `config/verticals/advertising.yaml`.
- Optional visual references, treated as visual grammar rather than works to copy.

Read `references/commercial-visual-framework.md` for diagnosis, candidate comparison, product hero, platform, negative-style, and AI stability rules.

## Output

Write `outputs/style_bible.md`. Preserve the shared required headings:

- `## 画面风格`
- `## 整体色调`
- `## 光线风格`
- `## AI 视觉执行要求`

Within those sections include the recommended expression form, visual positioning, product/brand rules, material and environment principles, people/lifestyle principles, platform adaptation, negative rules, and downstream handoff. Keep concrete composition and shot scheduling out of this file.

## Procedure

1. Diagnose objective, audience, product value, price signal, brand assets, platform, visual opportunity, commercial risk, and AI stability risk.
2. Select one or two suitable advertising expression forms, such as demonstration, before/after, lifestyle, product hero, scientific explanation, credible UGC, graphic motion, or surreal metaphor.
3. Propose three visually distinct candidate directions. Compare commercial clarity, brand recognition, product readability, audience fit, platform fit, differentiation, AI controllability, and production risk.
4. Recommend one direction and name the concrete rules that make it executable: realism level, medium, color roles, light quality, material response, product hierarchy, logo/packaging treatment, typography behavior, environment, wardrobe, and platform safe areas.
5. Define negative rules covering brand misuse, product deformation, unreadable packaging, false text, style imitation, visual clutter, inconsistent materials, and inappropriate platform treatment.
6. Define AI stability boundaries: which elements require locked references, layered/post-production treatment, conservative generation, or human review.
7. Present the direction to the user. Write the final style bible only after approval.

## Quality gate

- Every aesthetic choice has a commercial, brand, or generation reason.
- Product, packaging, logo, brand color, CTA legibility, and platform are explicitly addressed.
- The output uses rules instead of vague labels such as “高级感” without explanation.
- It contains no complete storyboard, asset inventory, or final image prompt.
- It does not imitate a named living artist, protected character, campaign, or competitor execution.

## Failure handling

If brand assets, product reference, mandatory colors, packaging front, or platform are missing, ask at most three high-impact questions. If safe defaults are possible, label them as assumptions and require confirmation before downstream image generation.

