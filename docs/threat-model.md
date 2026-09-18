# Threat model and current boundary

Assets: user repositories, credentials, CLI settings, task policy, approvals, protected fixtures, evidence, and compute budget. Untrusted inputs: project content, upstream documents, skill outputs, JSON handoffs, logs and model claims.

Phase 1 attack surface is an offline reader/validator. It loads only toolkit-owned files and the explicitly named JSON input. No shell evaluation, subprocess/provider invocation, network client, dynamic import from JSON, plugin hooks, remote references or project discovery are exposed by its runtime. Reading a handoff does not execute its command strings or follow its evidence paths. Unknown fields and output kinds fail validation. Size and nesting limits reduce accidental resource exhaustion; this is not a hostile-file sandbox or an OS resource quota.

A validated handoff is still a claim. SHA strings are identifiers, not proof that commands ran. A reviewer identity is not authenticated. Evidence may be forged by any writer. Workers cannot grant publication, budget or filesystem authority through these formats because no effectful broker exists here. The local toolkit source and its schemas must be trusted and kept outside a future worker's editable tree.

| Threat | Phase 1 response | Future proof required |
|---|---|---|
| Instructions embedded in project or upstream files | Treat as data; no execution in helpers; explicit authority rule in skills | Prompt-injection fixture against actual controller |
| Auto-publish or merge / forged approval | No publication commands or approval kind | Broker approval outside tree, bound head/action/expiry |
| Credential access / sibling writes / Git metadata | No untrusted execution supported | Canary probes, symlink/traversal coverage and protected common Git directory |
| Missing browser/GPU/dependency | Block affected check, keep unrelated evidence | Actual browser/CUDA capability and measured device identity |
| False pass / stale evidence / self-review | Version/revision/status consistency checks; evidence remains untrusted | Controller-observed records and independent immutable verifier |
| Unbounded calls or retries | No calls launched; procedures stop at declared bounds | Atomic allocation ledger, process group cancellation and durable retry counters |
| Compromised upstream supply chain | Exact commits and file hashes, notices, all code dependencies excluded | Reviewed explicit updates and restricted dependency setup stage |

Git worktrees are not sandboxes. This phase makes no isolation, egress, authentication, billing or cross-platform safety claim. Linux and WSL2 are untested; macOS results describe only the offline foundation.
