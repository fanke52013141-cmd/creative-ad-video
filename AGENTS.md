# Video Flow

This repository contains the general video execution standard and the inherited advertising V8 implementation.

- New runs use `python -m video_flow` and `config/workflow.yaml`, the sole stage/dependency source for the new standard. `config/pipeline.yaml` governs only V8 commands. Never mix checkpoints.
- The main agent owns routing, dispatch, acceptance and user decisions. Delegate professional tasks to fresh-context subagents using the generated task packet, selected skill and necessary references. User authorization includes delegation.
- Invoke the locked skill. Workers write their candidate and receipt; they cannot accept their own work or sign user approvals.
- Validate task IDs, input/skill hashes, schemas and independent review coverage. A pass label cannot override blocking issues or missing coverage.
- Distinguish mechanical validation from creative quality. Report unexecuted checks and unsupported routes honestly.
- Revisions are immutable; upstream changes invalidate descendants.
- V1 delivers preproduction text. Provider duration/frame/text/product restrictions belong to profiles, not the universal standard. No paid generation or publishing is implied.
- Use the user-supplied skill-building-expert for skill construction. Professional packages target 10,000-20,000 original Chinese characters across entrypoint, references and evaluation prose. Keep the entrypoint concise; do not pad or invent research/results.
- Keep real runs out of git; tests and committed examples use synthetic inputs.

Verification: `python -m unittest discover -s tests -v`; `python -m video_flow doctor`.
Legacy restrictions are documented in docs/legacy-advertising-rules.md.
