#!/usr/bin/env python3
"""Validate PipelineSpec references and enforce one canonical Skill per name."""
from __future__ import annotations

import json
import yaml

from pipeline_spec import REPO_ROOT, load_pipeline_spec, resolve_skill_path, resolve_stage_skill


def main() -> None:
    spec = load_pipeline_spec()
    resolved = {}
    errors = []
    template = yaml.safe_load((REPO_ROOT / "checkpoint.template.json").read_text(encoding="utf-8-sig"))
    if template.get("schema_version") != spec["schema_version"]:
        errors.append("checkpoint template schema_version does not match PipelineSpec")
    if "stages" in template or "phase_order" in template:
        errors.append("checkpoint template must not duplicate config-driven stage structure")
    default_aspect = spec["production_defaults"]["video_aspect_ratio"]
    if template.get("ad_production", {}).get("aspect_ratio") != default_aspect:
        errors.append("checkpoint default aspect ratio does not match PipelineSpec")
    duration = spec["production_constraints"]["video_segment_duration_seconds"]
    template_production = template.get("ad_production", {})
    if template_production.get("min_clip_seconds") != duration["minimum"] or template_production.get("max_clip_seconds") != duration["maximum"]:
        errors.append("checkpoint duration bounds do not match PipelineSpec")
    for schema_name in ("video_segment_plan.schema.json", "video_prompt_manifest.schema.json"):
        schema = json.loads((REPO_ROOT / "schemas" / schema_name).read_text(encoding="utf-8-sig"))
        item = schema["properties"]["segments" if schema_name.startswith("video_segment") else "videos"]["items"]
        field = item["properties"]["duration_seconds"]
        if field.get("minimum") != duration["minimum"] or field.get("maximum") != duration["maximum"]:
            errors.append(f"{schema_name} duration bounds do not match PipelineSpec")
    final_schema = json.loads((REPO_ROOT / "schemas" / "final_package_manifest.schema.json").read_text(encoding="utf-8-sig"))
    packaged_segment = final_schema["properties"]["artifacts"]["properties"]["video_segments"]["items"]
    packaged_duration = packaged_segment["properties"]["duration_seconds"]
    if packaged_duration.get("minimum") != duration["minimum"] or packaged_duration.get("maximum") != duration["maximum"]:
        errors.append("final_package_manifest.schema.json duration bounds do not match PipelineSpec")
    for stage in spec["stages"]:
        executor = stage["executor"]
        skill = resolve_stage_skill(stage, spec)
        if skill:
            try:
                skill_path = resolve_skill_path(skill)
                text = skill_path.read_text(encoding="utf-8-sig")
                if not text.startswith("---\n") or "\n---\n" not in text[4:]:
                    raise ValueError(f"invalid Skill frontmatter: {skill_path.relative_to(REPO_ROOT)}")
                frontmatter = yaml.safe_load(text.split("---", 2)[1]) or {}
                if frontmatter.get("name") != skill:
                    raise ValueError(f"Skill name mismatch: config={skill}, frontmatter={frontmatter.get('name')}")
                resolved[skill] = skill_path
            except (FileNotFoundError, ValueError) as exc:
                errors.append(str(exc))
        script = executor.get("script")
        if script and not (REPO_ROOT / script).is_file():
            errors.append(f"missing executor script: {script}")
        for output in stage.get("outputs", []):
            schema = output.get("schema")
            if schema and not (REPO_ROOT / "schemas" / schema).is_file():
                errors.append(f"{stage['id']} references missing schema: {schema}")
        if not stage.get("outputs"):
            errors.append(f"{stage['id']} must declare at least one trackable output")
    configured_skills = set(resolved)
    skill_dirs = {path.parent.name for path in (REPO_ROOT / ".agents" / "skills").glob("*/SKILL.md")}
    # run-ad-pipeline: flow-orchestration skill, invoked by the operator between stages, not by a stage executor.
    # advertising-idea-review: invoked by run-ad-pipeline before idea_generation approval; never a stage executor.
    orphan_skills = sorted(skill_dirs - configured_skills - {"run-ad-pipeline", "advertising-idea-review"})
    if orphan_skills:
        errors.append("orphan Skills not invoked by PipelineSpec: " + ", ".join(orphan_skills))
    consumer_text = "\n".join(
        path.read_text(encoding="utf-8-sig", errors="ignore")
        for folder in ("scripts", "config", "tests")
        for path in (REPO_ROOT / folder).rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".yaml", ".yml"}
    )
    unused_schemas = sorted(
        path.name for path in (REPO_ROOT / "schemas").glob("*.json")
        if path.name not in consumer_text
    )
    if unused_schemas:
        errors.append("schemas without a runtime/config/test consumer: " + ", ".join(unused_schemas))
    if errors:
        for error in errors:
            print("FAIL: " + error)
        raise SystemExit(1)
    for name, path in sorted(resolved.items()):
        print(f"OK skill {name}: {path.relative_to(REPO_ROOT)}")
    print(f"OK: {len(spec['stages'])} config-driven stages, {len(resolved)} unique skills")


if __name__ == "__main__":
    main()
