# Short Video Creation Pipeline

## Operating model

Run every project through the stable pipeline declared in `config/pipeline.yaml`. Select exactly one vertical profile from `config/verticals/` before generating content.

A vertical profile may replace strategy Skills and add quality gates. It must not replace stable infrastructure stages such as asset registration, image queue construction, image execution/import, result registration, checkpoint handling, or final packaging.

## Required execution order

1. Initialize a local run with `scripts/init_local_run.ps1`.
2. Select a vertical and write its id to `checkpoint.json` as `vertical.id`.
3. Resolve every `strategy_slot` through the selected vertical profile. Use `default_skill` when the profile does not override the slot.
4. Execute stages in `config/pipeline.yaml` order.
5. Stop at every configured approval gate. Do not let downstream stages consume an unapproved artifact.
6. Run the stage validator after each structured output and the full validator before final handoff.
7. Record repeated failures in `bad_cases/bad_case_log.yaml`.

## Stable contracts

- Story/content output: `outputs/story.md`. Vertical-specific business information (e.g. product, CTA, evidence) lives inside `story.md` under a dedicated section, not in a separate sidecar file.
- Art direction output: `outputs/style_bible.md`.
- Storyboard output: `outputs/storyboard.json`.
- Asset outputs: `outputs/asset_manifest.json` and `outputs/shot_asset_map.json`.
- Asset and storyboard image tasks share one image queue and one result manifest.
- Final downstream stages reference approved canonical asset paths, never arbitrary upload names.

## Vertical boundaries

Vertical Skills may decide narrative strategy, art constraints, storyboard strategy, prompt emphasis, and vertical-specific acceptance criteria. Put paths, durations, aspect ratios, required asset roles, and thresholds in the vertical YAML file instead of hard-coding them in Skill prose.

If a vertical override changes an existing output schema, stop and update the shared contract deliberately. Do not silently create a parallel pipeline.

## Verification

Use the bundled or system Python runtime:

```text
python scripts/validate_vertical_config.py
python scripts/validate_project.py <run-dir> --phase all
```

