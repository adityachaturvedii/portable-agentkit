# Phase 0–1 contract

Objective: ship a self-contained, reviewable skill foundation, not an execution controller.

Acceptance: all ten mapped skills and seven initial domain procedures are present; every skill has a narrow trigger, prerequisites, artifact schema, bounded stop conditions and linked procedures; upstream identities and attribution are preserved; each candidate has an explicit disposition; no undocumented executable dependencies are introduced. Offline validation rejects malformed and inconsistent proposals. Realistic disposable tasks exercise skill selection and produce useful evidence. Report observed capability and unverified behavior separately.

Non-goals: provider invocations, credential inspection, personal repositories, GPU connectivity, paid APIs, plugin installation, global settings, PR creation, pushing or merging. Python is the only runtime dependency; Git is needed for development, not pack usage. OS sandboxing and hostile input execution are not provided.

Interfaces: `python3 -m agentkit list`, `select INTENT`, `show SKILL [--domain PACK]`, `validate FILE`, `check`. Output selection is explicit and deterministic. Future `doctor`, `run`, `approve-pr`, etc. are intentionally unavailable. Handoff `schema_version=1` is an initial format; unknown versions, kinds and fields fail. A future schema change requires a versioned migration.

Budgets: Phase 1 helpers are offline and do not launch models or project commands. Procedure guidance requires declared resource bounds and checkpoints; actual budget enforcement remains planned. JSON inputs are size/depth bounded. File validation has no side effects.

Traceability: spec §4 → skills/ and domains/; §5 and §12 → contracts/; §10 → threat-model.md; §13 → checklist.md; §14 → tests/ and validation-report.md. The supplied spec remains unmodified at implementation-spec.md.
