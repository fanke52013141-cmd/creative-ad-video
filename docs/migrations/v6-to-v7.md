# V6 to V7 Migration

V7 separates immutable planning manifests from versioned media result manifests. V6 checkpoints are rejected until migrated.

## Procedure

```text
python scripts/migrate_run_v6_to_v7.py RUN_DIR --dry-run
python scripts/migrate_run_v6_to_v7.py RUN_DIR --apply
python scripts/validate_project.py RUN_DIR --level draft
```

The apply operation creates `.v6.bak` copies of the checkpoint, plan manifests and registries. It then:

1. Removes media and approval fields from asset and board plans.
2. Creates asset prompt, asset media and storyboard media manifests.
3. Re-registers existing files as V7 Artifact Revisions.
4. Recreates valid approvals against those revisions.
5. Generates checkpoint stages from PipelineSpec.
6. Invalidates `final_package`, which must be rebuilt under the V7 contract.

Do not delete backups until the migrated run passes the required validation level.

The current pipeline is V8. After this historical V6→V7 conversion, immediately run `scripts/migrate_run_v7_to_v8.py` and complete its semantic review requirements.
