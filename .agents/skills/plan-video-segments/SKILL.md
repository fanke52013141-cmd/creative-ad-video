---
name: plan-video-segments
description: Group ordered storyboard shots into deterministic AI-video segments and assign first, key and last frame roles.
---

# Plan Video Segments

Read `storyboard.json` and `references/expert-methodologies.md`, then create `outputs/video_segment_plan.json` conforming to `schemas/video_segment_plan.schema.json`. Every shot must be covered exactly once, source shots must remain contiguous and within one scene, and every segment must be between 4 and 30 seconds inclusive.

When a candidate segment is shorter than 4 seconds, merge it with an adjacent contiguous segment in the same scene. Never cross a scene boundary, invent dead time or change shot durations merely to satisfy the minimum. If no legal merge exists, stop and request a storyboard timing revision.

Do not generate storyboard prompts, media or video prompts.
