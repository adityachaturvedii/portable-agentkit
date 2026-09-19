# Local PR proposal — not published

Title: Add audited portable skill foundation and offline handoff validation

The engineering plan needed a reusable foundation before provider execution or orchestration. This change pins the three upstream skill repositories, records file hashes and dependency/authority exclusions, retains MIT notices, and adapts ten focused engineering skills with seven initial domain procedures. A Python standard-library helper exposes offline discovery, rendering and strict versioned handoff validation. It does not execute project commands, call providers or authorize external effects.

Validation uses disposable CPU projects with planted defects, negative handoff cases, a relocated copy with an empty HOME, and an independent skills-versus-native invoice exercise. Both agent conditions solved the API defect and reported missing browser verification honestly; no general performance or quality advantage is established. See validation-report.md for evidence and limitations, and checklist.md for phase status.

Phase 2 CLI/sandbox feasibility, durable orchestration, approvals, budgets, GPU and GitHub integration remain planned. Credential isolation has not been proven, so unattended untrusted execution is unsupported. Original toolkit licensing is deferred until distribution; adapted material retains its upstream MIT notices.

Repository: new standalone local `portable-agentkit` repository.
Branch: `implementation/phase-0-1` in dedicated `portable-agentkit-phase01` worktree.
Base: `0a1394f` (empty bootstrap commit; full SHA in local receipt).
Candidate head: recorded outside the worktree in the final local receipt to avoid a self-referential commit hash.

Approval status: none. No remote is configured. This proposal does not authorize push/PR creation. A later user approval must identify repository, branch, exact current head and publication action; merge requires separate authority. The Phase 3 broker that enforces this has not yet been implemented.
