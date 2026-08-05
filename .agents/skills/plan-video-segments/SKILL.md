---
name: plan-video-segments
description: Group ordered storyboard shots into deterministic AI-video segments and assign first, key and last frame roles.
---

# Plan Video Segments

Read `storyboard.json` and `references/expert-methodologies.md`, then create `outputs/video_segment_plan.json` conforming to `schemas/video_segment_plan.schema.json`. Every shot must be covered exactly once, source shots must remain contiguous and within one scene, and every segment must be between 4 and 30 seconds inclusive.

When a candidate segment is shorter than 4 seconds, resolve it in this order:

1. **Merge first.** Merge it with an adjacent contiguous segment in the same scene. Never cross a scene boundary, never invent dead time, and never drop or reorder shots.
2. **Adjust durations second.** If no legal merge exists (e.g. the scene is a single short shot with no same-scene neighbour), you may extend the duration of one or more shots in the segment to reach the 4-second minimum. Extend by increasing `duration_seconds` in `storyboard.json` for the affected shots, staying within each shot's schema limit (each shot ≤ 10 seconds). When the project declares a target total duration in `checkpoint.ad_production.duration_seconds`, compensate by trimming other shots in the same scene so the storyboard total still matches the target within 0.5s — otherwise `validate_storyboard` will reject the run. Record the adjustment in `merge_reason` as a duration-extension fallback.
3. **Escalate last.** Only if neither a merge nor a duration extension can produce a legal segment, stop and request a storyboard timing revision.

Duration extension is a fallback, not the default: prefer merging whenever a same-scene neighbour exists.

Do not generate storyboard prompts, media or video prompts.
