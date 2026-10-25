# Video Flow

This repository contains the general video execution standard and the inherited advertising V8 implementation.

- New runs use `python -m video_flow` and `config/workflow.yaml`, the sole stage/dependency source for the new standard. `config/pipeline.yaml` governs only V8 commands. Never mix checkpoints.
- The main agent owns routing, dispatch, acceptance and user decisions. Delegate professional tasks to fresh-context subagents using the generated task packet, selected skill and necessary references. User authorization includes delegation.
- Invoke the locked skill. Workers write their candidate and receipt; they cannot accept their own work or sign user approvals.
- Validate task IDs, input/skill hashes, schemas and independent review coverage. A pass label cannot override blocking issues or missing coverage.
- Distinguish mechanical validation from creative quality. Report unexecuted checks and unsupported routes honestly.
- Revisions are immutable; upstream changes invalidate descendants.
- V1 delivers preproduction text. Provider duration/frame/text/product restrictions belong to profiles, not the universal standard. No paid generation or publishing is implied.
- V0.2 is explicitly selected with --production-config and --media; read docs/contracts-v02.md. It delivers portable TXT/reference-image packages using reviewed imports or offline mock fixtures. Paid image-provider execution and external video generation are not enabled by this selection.
- Imported story sources must be hash-verified and shared with both writer and reviewer. Deterministic media import uses its declared import operation identity; do not fabricate a spawned agent identity.
- Media fanout (`--media` runs) is one bounded task per item: dispatch a single item, spawn a fresh worker per item, one image per task. Revisions reopen only cited items; never merge items into one image or one context.
- Use the user-supplied skill-building-expert for skill construction. Professional packages target 10,000-20,000 original Chinese characters across entrypoint, references and evaluation prose. Keep the entrypoint concise; do not pad or invent research/results.
- Keep real runs out of git; tests and committed examples use synthetic inputs.

Verification: `python -m unittest discover -s tests -v`; `python -m video_flow doctor`.
Legacy restrictions are documented in docs/legacy-advertising-rules.md.
