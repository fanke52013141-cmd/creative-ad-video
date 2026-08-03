# Creative Ad Video Pipeline

## Operating model

`config/pipeline.yaml` is the only source of truth for stages, dependencies, executors, approval requirements, skip policy and declared artifacts. Do not hard-code a competing stage list in prose or new scripts.

## Required execution

1. Initialize a run with `scripts/init_local_run.ps1`.
2. Inspect and materialize ready DAG nodes through `scripts/pipeline_engine.py`.
3. For Codex tasks, invoke exactly the `resolved_skill` written in the task manifest.
4. Register stage outputs as immutable Artifact Revisions before completion.
5. Stop at every configured approval gate. Story, art direction and storyboard must be approved.
6. Build V/SB/S relationships only with `build_storyboard_packets.py` and `build_video_prompt_manifest.py`.
7. Never let downstream code infer business relations through directory order or the first glob result.
8. Media generation may be replaced by manual import. A draft-only skip cannot pass production validation.
9. Package only explicit, approved manifest references.
10. Never add media paths, hashes, revisions or approval state to `asset_manifest.json` or `storyboard_board_manifest.json`; use the corresponding media manifest.
11. Every `V###` video generation unit must be 4-30 seconds. Short `S###` shots remain valid and must be merged without crossing scene boundaries or inventing padding.
12. Video generation references are limited to approved storyboard boards, characters and advertised products. Never pass scene, set-dressing, effect or ordinary-prop assets to the video model.
13. Advertising text must be declared on a storyboard shot, rendered in its board and text-verified before board approval. Post-production text fallback is forbidden.
14. Use the project aspect ratio; when none is declared, use the PipelineSpec default `16:9` and carry it into every video prompt and package.

## Integrity and approval

- Approval binds to an Artifact Revision and SHA-256.
- Never edit an approved snapshot.
- A canonical artifact hash mismatch blocks downstream execution and creates a new revision requirement.
- Use `approve_media.py` for generated assets and storyboard boards.
- Treat `asset_media_manifest.json` and `storyboard_media_manifest.json` as indexes of registered revisions, never as approval stores.
- Persist blockers and rejection reasons in checkpoint/event state; do not rely on conversation memory.

## Verification

```text
python scripts/validate_pipeline_contract.py
python -m unittest discover -s tests -v
python scripts/validate_project.py RUN_DIR --level draft
python scripts/validate_project.py RUN_DIR --level production
python scripts/validate_project.py RUN_DIR --level delivery
```

Only `--level delivery` authorizes final handoff. `--phase all` is deprecated and intentionally fails.

## Repository policy

Do not commit `local_runs/`, real client materials, generated media, secrets or private checkpoints. Reusable failures belong in `bad_cases/bad_case_log.yaml` with a regression check.
