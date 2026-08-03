# V7 to V8 Migration

V8 makes the storyboard board the static visual source of truth, limits video units to 4–30 seconds, defaults unspecified video aspect ratios to 16:9, and restricts video references to boards, characters and advertised products.

## Procedure

```text
python scripts/migrate_run_v7_to_v8.py RUN_DIR --dry-run
python scripts/migrate_run_v7_to_v8.py RUN_DIR --apply
```

Apply creates `.v7.bak` files before modifying current contracts.

## Required review after migration

1. Review every shot added to `text_contract_review_required`; V7 had no structured advertising-text field, so the migration cannot safely infer copy from prose.
2. Review every prop in `product_classification_review_required`. The migration defaults unknown props to `story_prop`; never auto-promote a prop to an advertised product.
3. Fix every segment in `invalid_video_segments` by merging adjacent shots in the same scene or revising storyboard timing.
4. Regenerate and approve storyboard prompts/media with explicit text verification.
5. Regenerate video prompts so they contain no scene or non-product references and explicitly state the project aspect ratio.
6. Rebuild the final package.

V6 runs must first use `migrate_run_v6_to_v7.py`, then run this migration.
