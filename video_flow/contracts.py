"""Deterministic domain checks; they do not grade creative merit."""
from __future__ import annotations
import math


class FlowError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FlowError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def brief_check(brief):
    require(isinstance(brief, dict), "brief must be an object")
    for field in ("title", "goal", "narrative_form", "distribution", "production_mode", "style"):
        require(text(brief.get(field)), f"brief requires {field}")
    require(number(brief.get("duration_seconds")) and brief["duration_seconds"] > 0, "duration must be positive")
    require(type(brief.get("episode_count")) is int and brief["episode_count"] > 0, "episode_count must be positive integer")
    require(isinstance(brief.get("constraints"), list) and all(text(x) for x in brief["constraints"]), "constraints must be strings")
    require(isinstance(brief.get("facts"), list), "brief facts must be an array")
    require(brief['narrative_form'] in {'standalone', 'serial', 'documentary', 'display'}, 'unknown narrative_form')
    require(brief['goal'] in {'brand', 'conversion', 'art', 'entertainment', 'public', 'knowledge'}, 'unknown goal')
    for fact in brief["facts"]:
        require(isinstance(fact, dict) and text(fact.get("claim")) and text(fact.get("source")), "facts need claim and source")


FIELDS = {
    "story": ["scene_goal", "action", "duration_seconds"],
    "style": ["axis", "rule", "story_reason"],
    "storyboard": ["scene_id", "beat", "action", "start_state", "end_state", "duration_seconds", "axis", "cut_motivation", "sound"],
    "assets": ["kind", "description", "shot_ids", "continuity_rules"],
    "edit_sound": ["shot_id", "picture_cut", "sound", "motivation"],
    "media_item": ["item", "file", "sha256", "prompt"],
}


def artifact_check(value, kind, inputs):
    require(isinstance(value, dict) and value.get("type") == kind, f"expected artifact type {kind}")
    items = value.get("items")
    require(isinstance(items, list) and items, "artifact items must not be empty")
    ids = [row.get("id") for row in items if isinstance(row, dict)]
    require(len(ids) == len(items) and all(text(x) for x in ids) and len(set(ids)) == len(ids), "item ids must be nonempty and unique")
    for row in items:
        for field in FIELDS[kind]:
            cell = row.get(field)
            if field == "duration_seconds":
                require(number(cell) and cell > 0, "duration_seconds must be positive")
            elif field == "shot_ids":
                require(isinstance(cell, list) and cell and all(text(x) for x in cell), "shot_ids must be nonempty")
            else:
                require(text(cell), f"{row['id']} missing {field}")
    if kind in {"story", "storyboard"}:
        total = sum(x["duration_seconds"] for x in items)
        require(abs(total - inputs["brief"]["duration_seconds"]) <= 0.5, "duration does not match brief")
    if kind == "storyboard":
        scenes = {x["id"] for x in inputs["story"]["items"]}
        require({x["scene_id"] for x in items} == scenes, "storyboard must cover exactly the story scenes")
    if kind in {"assets", "edit_sound"}:
        shots = {x["id"] for x in inputs["storyboard"]["items"]}
        refs = {s for x in items for s in x["shot_ids"]} if kind == "assets" else {x["shot_id"] for x in items}
        require(refs == shots, "output must cover exactly the storyboard shot ids")


def media_item_check(value):
    """One task, one image: a worker candidate for a single fanout media item."""
    require(isinstance(value, dict) and value.get("type") == "media_item", "expected artifact type media_item")
    for field in FIELDS["media_item"]:
        require(text(value.get(field)), f"media item requires {field}")
    require(len(value["sha256"]) == 64 and all(c in "0123456789abcdef" for c in value["sha256"]), "sha256 must be a 64-char hex digest")
    require(not value["file"].startswith(("/", "\\")) and ".." not in value["file"], "media file must be a safe run-relative path")


def media_check(value, expected_items):
    """Assembled fanout artifact: exactly the queued items, each with its own image."""
    require(isinstance(value, dict) and value.get("type") == "media", "expected artifact type media")
    items = value.get("items")
    require(isinstance(items, list) and items, "media items must not be empty")
    ids = [x.get("item") for x in items]
    require(all(text(x) for x in ids) and len(set(ids)) == len(ids), "media item ids must be nonempty and unique")
    require(set(ids) == set(expected_items), "media must cover exactly the queued items")
    for row in items:
        for field in ("file", "sha256", "prompt"):
            require(text(row.get(field)), f"{row.get('item')} missing {field}")


def review_check(review, target, target_hash, required_criteria):
    require(review.get("type") == "review", "expected review")
    require(review.get("target_sha256") == target_hash, "review target hash mismatch")
    expected = {x.get("id") or x.get("item") for x in target["items"]}
    coverage = review.get("coverage")
    require(isinstance(coverage, list) and all(text(x) for x in coverage), "invalid review coverage")
    require(len(coverage) == len(set(coverage)) and set(coverage) == expected, "review must cover exactly all target items")
    issues = review.get("issues")
    require(isinstance(issues, list), "review requires issues")
    for issue in issues:
        require(isinstance(issue, dict) and issue.get("severity") in {"P0", "P1", "P2"}, "invalid severity")
        require(text(issue.get("location")) and text(issue.get("reason")), "issues require location/reason")
    criteria = review.get("criteria")
    require(isinstance(criteria, list) and criteria, "review requires evidence-backed criteria")
    for criterion in criteria:
        require(isinstance(criterion, dict), "criterion must be an object")
        require(text(criterion.get("name")) and text(criterion.get("evidence")), "criterion needs name/evidence")
        require(type(criterion.get("score")) is int and 0 <= criterion["score"] <= 4, "score must be 0-4")
    require(review.get("verdict") in {"pass", "revise"}, "invalid verdict")
    if review["verdict"] == "pass":
        require(not any(x["severity"] in {"P0", "P1"} for x in issues), "pass cannot contain P0/P1")
        require(all(x["score"] >= 3 for x in criteria), "pass cannot contain scores below 3")
    names = [x['name'] for x in criteria]
    require(len(names) == len(set(names)) and set(names) == set(required_criteria), 'review must cover exactly the required criteria')
