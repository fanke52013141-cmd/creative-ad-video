"""Immutable artifact revisions and hash-bound approvals."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from path_safety import relative_to_run, resolve_in_run
from pipeline_spec import stage_map


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _load(path: Path, root_key: str) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": "1.0", root_key: []}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get(root_key), list):
        raise ValueError(f"invalid registry: {path}")
    return data


def artifact_registry_path(run: Path) -> Path:
    return run / "outputs" / "artifact_registry.json"


def approval_registry_path(run: Path) -> Path:
    return run / "outputs" / "approval_registry.json"


def digest_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    elif path.is_dir():
        for child in sorted(x for x in path.rglob("*") if x.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(child.read_bytes())
            digest.update(b"\0")
    else:
        raise ValueError(f"artifact is neither file nor directory: {path}")
    return "sha256:" + digest.hexdigest()


def _declared_revision_references(path: Path) -> list[str]:
    if not path.is_file() or path.suffix.lower() != ".json":
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    found = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.endswith("_revision_id") and isinstance(child, str):
                    found.append(child)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return found


def register_stage_artifacts(run: Path, checkpoint: dict[str, Any], stage: str) -> list[str]:
    run = run.resolve()
    registry_path = artifact_registry_path(run)
    registry = _load(registry_path, "artifacts")
    dependencies = []
    spec = stage_map()[stage]
    for dependency in spec["depends_on"]:
        dependencies.extend(checkpoint["stages"].get(dependency, {}).get("artifact_revision_ids", []))
    revision_ids = []
    for output in spec.get("outputs", []):
        source = resolve_in_run(run, output["path"], must_exist=True)
        existing = [x for x in registry["artifacts"] if x["stage"] == stage and x["artifact_name"] == output["name"]]
        revision = max((x["revision"] for x in existing), default=0) + 1
        revision_id = f"{output['name']}:r{revision:03d}"
        suffix = "".join(source.suffixes) if source.is_file() else ""
        snapshot = run / "outputs" / "versions" / output["name"] / f"{output['name']}.v{revision:03d}{suffix}"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists():
            raise ValueError(f"artifact snapshot already exists: {snapshot}")
        if source.is_dir():
            shutil.copytree(source, snapshot)
        else:
            shutil.copy2(source, snapshot)
        row = {
            "artifact_revision_id": revision_id,
            "artifact_name": output["name"],
            "stage": stage,
            "revision": revision,
            "canonical_path": relative_to_run(run, source),
            "snapshot_path": relative_to_run(run, snapshot),
            "sha256": digest_path(source),
            "dependencies": sorted(set(dependencies + _declared_revision_references(source))),
            "created_at": now(),
        }
        registry["artifacts"].append(row)
        revision_ids.append(revision_id)
    _atomic_json(registry_path, registry)
    return revision_ids


def latest_stage_revisions(run: Path, stages: list[str]) -> list[str]:
    registry = _load(artifact_registry_path(run.resolve()), "artifacts")
    return [
        row["artifact_revision_id"]
        for row in registry["artifacts"]
        if row["stage"] in stages
        and row["revision"] == max(
            candidate["revision"]
            for candidate in registry["artifacts"]
            if candidate["stage"] == row["stage"] and candidate["artifact_name"] == row["artifact_name"]
        )
    ]


def register_media_artifact(
    run: Path,
    *,
    artifact_name: str,
    stage: str,
    source: Path,
    dependencies: list[str] | None = None,
) -> dict[str, Any]:
    """Register an immutable media revision without mutating an upstream plan manifest."""
    run = run.resolve()
    source = source.resolve()
    source.relative_to(run)
    registry_path = artifact_registry_path(run)
    registry = _load(registry_path, "artifacts")
    existing = [row for row in registry["artifacts"] if row["artifact_name"] == artifact_name]
    revision = max((row["revision"] for row in existing), default=0) + 1
    revision_id = f"{artifact_name}:r{revision:03d}"
    snapshot = run / "outputs" / "versions" / artifact_name / f"{artifact_name}.v{revision:03d}{source.suffix.lower()}"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if snapshot.exists():
        raise ValueError(f"artifact snapshot already exists: {snapshot}")
    shutil.copy2(source, snapshot)
    row = {
        "artifact_revision_id": revision_id,
        "artifact_name": artifact_name,
        "stage": stage,
        "revision": revision,
        "canonical_path": relative_to_run(run, source),
        "snapshot_path": relative_to_run(run, snapshot),
        "sha256": digest_path(source),
        "dependencies": sorted(set(dependencies or [])),
        "created_at": now(),
    }
    registry["artifacts"].append(row)
    _atomic_json(registry_path, registry)
    return row


def _artifacts_by_id(run: Path) -> dict[str, dict[str, Any]]:
    registry = _load(artifact_registry_path(run), "artifacts")
    return {row["artifact_revision_id"]: row for row in registry["artifacts"]}


def verify_stage_integrity(run: Path, checkpoint: dict[str, Any], stage: str) -> list[str]:
    revision_ids = checkpoint["stages"].get(stage, {}).get("artifact_revision_ids", [])
    if not revision_ids:
        return []
    errors = []
    for revision_id in revision_ids:
        errors.extend(verify_artifact_revision(run, revision_id))
    return errors


def approve_stage_artifacts(run: Path, checkpoint: dict[str, Any], stage: str, actor: str, comment: str) -> list[str]:
    revision_ids = checkpoint["stages"][stage].get("artifact_revision_ids", [])
    if not revision_ids:
        raise ValueError(f"{stage} has no registered artifact revisions")
    integrity = verify_stage_integrity(run, checkpoint, stage)
    if integrity:
        raise ValueError("; ".join(integrity))
    artifacts = _artifacts_by_id(run)
    path = approval_registry_path(run)
    registry = _load(path, "approvals")
    approval_ids = []
    for revision_id in revision_ids:
        row = artifacts[revision_id]
        approval_id = f"APR-{len(registry['approvals']) + 1:06d}"
        registry["approvals"].append({
            "approval_id": approval_id,
            "artifact_revision_id": revision_id,
            "artifact_sha256": row["sha256"],
            "stage": stage,
            "actor": actor,
            "decision": "approved",
            "comment": comment,
            "created_at": now(),
        })
        approval_ids.append(approval_id)
    _atomic_json(path, registry)
    return approval_ids


def approve_artifact_revision(
    run: Path,
    revision_id: str,
    actor: str,
    comment: str,
    evidence: dict[str, Any] | None = None,
) -> str:
    artifacts = _artifacts_by_id(run.resolve())
    row = artifacts.get(revision_id)
    if not row:
        raise ValueError(f"missing artifact revision: {revision_id}")
    integrity_errors = verify_artifact_revision(run, revision_id)
    if integrity_errors:
        raise ValueError("; ".join(integrity_errors))
    path = approval_registry_path(run.resolve())
    registry = _load(path, "approvals")
    approval_id = f"APR-{len(registry['approvals']) + 1:06d}"
    approval = {
        "approval_id": approval_id,
        "artifact_revision_id": revision_id,
        "artifact_sha256": row["sha256"],
        "stage": row["stage"],
        "actor": actor,
        "decision": "approved",
        "comment": comment,
        "created_at": now(),
    }
    if evidence is not None:
        approval["evidence"] = evidence
    registry["approvals"].append(approval)
    _atomic_json(path, registry)
    return approval_id


def verify_artifact_revision(run: Path, revision_id: str) -> list[str]:
    artifacts = _artifacts_by_id(run.resolve())
    errors = []
    visited = set()

    def visit(current_id: str) -> None:
        if current_id in visited:
            return
        visited.add(current_id)
        row = artifacts.get(current_id)
        if not row:
            errors.append(f"missing artifact revision: {current_id}")
            return
        try:
            canonical = resolve_in_run(run, row["canonical_path"], must_exist=True)
            if digest_path(canonical) != row["sha256"]:
                errors.append(f"artifact modified after registration: {current_id}")
            snapshot = resolve_in_run(run, row["snapshot_path"], must_exist=True)
            if digest_path(snapshot) != row["sha256"]:
                errors.append(f"artifact snapshot modified after registration: {current_id}")
        except ValueError as exc:
            errors.append(str(exc))
        for dependency in row.get("dependencies", []):
            visit(dependency)

    visit(revision_id)
    return errors


def verify_artifact_approval(run: Path, revision_id: str) -> list[str]:
    artifacts = _artifacts_by_id(run.resolve())
    row = artifacts.get(revision_id)
    if not row:
        return [f"missing artifact revision: {revision_id}"]
    errors = verify_artifact_revision(run, revision_id)
    registry = _load(approval_registry_path(run.resolve()), "approvals")
    approvals = [
        approval for approval in registry["approvals"]
        if approval["artifact_revision_id"] == revision_id
    ]
    if not approvals or approvals[-1]["decision"] != "approved":
        errors.append(f"missing approval for {revision_id}")
    elif approvals[-1]["artifact_sha256"] != row["sha256"]:
        errors.append(f"stale approval for {revision_id}")
    return errors


def verify_storyboard_text_approval(run: Path, revision_id: str, required_text: list[str]) -> list[str]:
    """Require a hash-bound board approval with explicit text/extra-text verification."""
    errors = verify_artifact_approval(run, revision_id)
    registry = _load(approval_registry_path(run.resolve()), "approvals")
    approvals = [
        approval for approval in registry["approvals"]
        if approval["artifact_revision_id"] == revision_id and approval["decision"] == "approved"
    ]
    if not approvals:
        return errors
    verification = approvals[-1].get("evidence", {}).get("text_verification")
    if not verification:
        errors.append(f"missing storyboard text verification for {revision_id}")
        return errors
    if verification.get("declared_text") != required_text:
        errors.append(f"storyboard declared text evidence mismatch for {revision_id}")
    if verification.get("verified_text") != required_text or verification.get("exact_match") is not True:
        errors.append(f"storyboard text does not exactly match declaration for {revision_id}")
    if verification.get("extra_text_absent") is not True:
        errors.append(f"storyboard contains unapproved extra text for {revision_id}")
    return errors


def verify_stage_approvals(run: Path, checkpoint: dict[str, Any], stage: str) -> list[str]:
    revision_ids = checkpoint["stages"].get(stage, {}).get("artifact_revision_ids", [])
    if not revision_ids:
        return []
    artifacts = _artifacts_by_id(run)
    registry = _load(approval_registry_path(run), "approvals")
    errors = []
    for revision_id in revision_ids:
        artifact = artifacts.get(revision_id)
        matches = [x for x in registry["approvals"] if x["artifact_revision_id"] == revision_id and x["decision"] == "approved"]
        if not matches:
            errors.append(f"missing approval for {revision_id}")
        elif not artifact or matches[-1]["artifact_sha256"] != artifact["sha256"]:
            errors.append(f"stale approval for {revision_id}")
    return errors
