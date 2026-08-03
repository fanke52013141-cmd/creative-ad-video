---
name: run-ad-pipeline
description: Continue a creative advertising video run through the config-driven DAG. Use to inspect ready stages, execute Codex Skill tasks, pause at approval gates, retry failed tasks, and preserve artifact lineage.
---

# Run Ad Pipeline

## Contract

Input: one initialized local run directory.

Output: registered stage artifacts, checkpoint transitions, approvals or a concrete blocker/next user action.

## Procedure

1. Run `python scripts/pipeline_engine.py RUN_DIR ready`.
2. For a ready stage, run `python scripts/pipeline_engine.py RUN_DIR run --stage STAGE`.
3. If the engine executes a script handler, inspect its exit status and continue.
4. If it returns `execute_stage_task`, read the emitted task file and invoke exactly the `resolved_skill` named there.
5. Write only the task's expected outputs. Do not invent parallel artifact paths.
6. Build deterministic manifests when entering their stages:
   - `python scripts/build_storyboard_packets.py RUN_DIR`
   - `python scripts/build_video_prompt_manifest.py RUN_DIR`
7. Complete the stage through `run_pipeline.py`; stop at `review_required` and ask the designated human to approve the registered revision.
8. Before approving `idea_generation`, run the creative review: invoke `advertising-idea-review` on `outputs/brief.md` and `outputs/story.md`. It presents a graded diagnosis in the conversation and writes `outputs/idea_review_feedback.md` for the revision loop. The review only advises; it never approves or blocks.
9. After the review, the human decides: `approve` to pass the revision, or `reject` (use `--reason` pointing to `outputs/idea_review_feedback.md`) to start a revision round. The revision round re-runs `advertising-idea-strategy`, which reads the feedback file and revises the plan. A revised plan is NOT re-reviewed automatically; re-review happens only when the human asks for it.
10. Use `skip` only on stages whose PipelineSpec permits it and always provide a reason. A draft-only skip cannot pass production validation.
11. On failure, preserve the task, checkpoint blocker and provider result. Retry instead of recreating completed work.

## Integrity Rules

- Consume only declared dependency Artifact Revisions.
- Never edit an approved artifact snapshot.
- Never infer V/SB/S relations from filenames or directory order.
- A hash mismatch blocks downstream execution and requires a new revision.
- Final handoff requires `--level delivery`.
- `outputs/idea_review_feedback.md` is workflow state, not a deliverable: it never enters Artifact/Approval Registries, never appears in the final package, and is not checked by `validate_project.py`.
