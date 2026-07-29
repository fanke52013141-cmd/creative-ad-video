---
name: video-segment-planner
description: Group consecutive storyboard shots into minimal AI-video generation segments and assign first-frame, last-frame and keyframe roles. Use after approved assets and before storyboard prompt generation. Do not write image or video prompts.
---

# Video Segment Planner

## Goal

Create the smallest necessary set of independently generatable video segments without sacrificing continuity.

Read `references/expert_methodologies.md` section `Shot joining` before planning.

## Inputs and output

```json
{
  "storyboard_path": "./outputs/storyboard.json",
  "shot_asset_map_path": "./outputs/shot_asset_map.json",
  "output_path": "./outputs/video_segment_plan.json",
  "max_segment_seconds": "{从vertical配置的max_generated_clip_seconds注入}"
}
```

## Decision process

1. Start with one shot per segment.
2. Consider only the next consecutive shot with the same `scene_id`.
3. Merge only when action phase, screen direction, placement or one camera move forms a genuinely continuous unit and total duration stays within the limit.
4. Keep separate when there is a real cut purpose: subject, viewpoint, focal information, reaction, time, space or narrative unit changes.
5. Stop adding frames when an intermediate reference has no material continuity value.
6. Assign one-shot segments `first_frame` only. For multi-shot segments assign first/last to endpoints and `keyframe` to necessary middle shots.
7. Write `video_segment_plan.json` conforming to its schema.

## Quality gate

- Cover every shot once and in order.
- Never merge across scenes or over the duration limit.
- Require a concrete continuity reason for every merge.
- Prefer fewer necessary frames, not fewer frames at the expense of control.
