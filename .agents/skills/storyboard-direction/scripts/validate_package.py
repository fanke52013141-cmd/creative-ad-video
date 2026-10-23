"""Mechanical regression for the two in-package synthetic cases.

Validates the coffee and silent fixtures against the repository's
video_flow/contracts.py (brief, story, storyboard) and runs six fault
injection classes that must be rejected. Results are written to
evaluation/mechanical-report.json. This mechanical pass is not a
creative-quality or research-completeness score.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]   # .agents/skills/storyboard-direction
ROOT = PKG.parents[2]                       # repository root
sys.path.insert(0, str(ROOT))

from video_flow import contracts  # noqa: E402

CASES = ("coffee", "silent")


def load(case, kind):
    return json.loads((PKG / "evaluation" / f"{case}-{kind}.json").read_text(encoding="utf-8"))


def check_case(case):
    data = load(case, "inputs")
    artifact = load(case, "artifact")
    contracts.brief_check(data["brief"])
    contracts.artifact_check(data["story"], "story", data)
    contracts.artifact_check(artifact, "storyboard", data)
    return {
        "shots": len(artifact["items"]),
        "duration_seconds": sum(x["duration_seconds"] for x in artifact["items"]),
        "scenes": sorted({x["scene_id"] for x in artifact["items"]}),
    }


def expect_reject(label, mutate):
    data = load("coffee", "inputs")
    artifact = load("coffee", "artifact")
    inputs = {"brief": data["brief"], "story": data["story"]}
    mutate(artifact)
    try:
        contracts.artifact_check(artifact, "storyboard", inputs)
    except contracts.FlowError:
        return {"case": label, "rejected": True}
    raise SystemExit(f"fault injection not rejected: {label}")


def drop_field(artifact):
    del artifact["items"][0]["sound"]


def blank_field(artifact):
    artifact["items"][0]["action"] = "   "


def dup_id(artifact):
    artifact["items"][1]["id"] = artifact["items"][0]["id"]


def unknown_scene(artifact):
    artifact["items"][0]["scene_id"] = "SC99"


def zero_duration(artifact):
    artifact["items"][0]["duration_seconds"] = 0


def drift_total(artifact):
    artifact["items"][0]["duration_seconds"] += 1


FAULTS = (
    ("missing sound", drop_field),
    ("blank action", blank_field),
    ("duplicate id", dup_id),
    ("unknown scene", unknown_scene),
    ("zero duration", zero_duration),
    ("duration total drift", drift_total),
)


def main():
    report = {"cases": {}, "fault_injections": []}
    for case in CASES:
        report["cases"][case] = check_case(case)
    for label, mutate in FAULTS:
        report["fault_injections"].append(expect_reject(label, mutate))
    out = PKG / "evaluation" / "mechanical-report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
