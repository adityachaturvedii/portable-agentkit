# Implementation checklist

## Phase 0

- [x] Read and preserve the supplied implementation specification.
- [x] Create a fresh repository, dedicated branch and linked worktree; no remote.
- [x] Pin all three candidate skill repositories to full commits and archive hashes.
- [x] Inspect candidate files, referenced procedures, licenses, manifests and install surfaces.
- [x] Record per-file hashes and adopt/adapt/reject decisions; retain MIT notices.
- [x] Define Phase 1 requirements and threat model; distinguish future enforcement.

## Phase 1

- [x] Ten portable core skills with narrow triggers, prerequisites, outputs and stop conditions.
- [x] Seven initial domain procedures, loaded only when relevant.
- [x] Structured, versioned JSON handoffs and fail-closed offline validation.
- [x] Offline catalog, explicit intent selection, skill rendering and package checks.
- [x] Disposable synthetic tasks, negative contract cases and independent forward evaluation.
- [x] Document adaptations, tested platform, limitations and local PR proposal.

## Phase 2 — feasibility implementation

- [x] Verify exact `72a3ccd` base, clean prior tree and all 29 foundation tests; create separate branch/worktree.
- [x] Read-only doctor with version/feature/auth/sandbox states; no global config changes.
- [x] Provider-neutral v1 records, separate wire adapters, redacted raw evidence and nullable usage.
- [x] Bounded process supervision, cancellation and same-group child cleanup.
- [x] Disposable failure fixtures and independent output oracle; no deliberate live quota exhaustion.
- [x] Real fake-credential, symlink, sibling, common Git metadata, loopback and process canaries.
- [x] One Claude live subscription call; accepted by corrected offline replay, original false-positive record retained.
- [x] Attempt Codex smoke under restrictions; preserve startup failure without relaxing guard.
- [x] Matrix, usage limitations, evidence, decisions and Phase 3 recommendation.
- [x] Both engines complete a disposable live coding task under the follow-up external filesystem guard.
- [ ] Tool-enabled credential/egress isolation: **unsupported**, not implied by native CLI sandbox flags.

## Phase 2 execution follow-up

- [x] Verify clean exact `6bfb981670a1f4e553c870995414452f2ce06b21`; create `implementation/phase-2-execution` in a dedicated worktree.
- [x] Diagnose Codex startup to its writable lock on literal `~/.codex/installation_id`; verify unchanged hash/size/mode.
- [x] Diagnose and narrowly contain Claude session-env and temporary-state writes without changing auth or global settings.
- [x] Complete both live disposable coding tasks and independently verify the exact test command, changed-file manifest and immutable test.
- [x] Deny read/write access to sibling workspace, fake credentials and controller state under the exact external profile.
- [x] Verify timeout, cancellation and TERM-resistant same-group child cleanup under that profile.
- [x] Preserve failed attempts and nullable usage; distinguish Claude CLI cost estimates from billing.
- [x] Approve trusted disposable-workspace mode for Phase 3 design on the tested host.
- [ ] Tool-network separation, comprehensive credential isolation and hostile/untrusted local execution: **blocked**.
- [ ] Detached descendants, remote cancellation and controller crash recovery: **unsupported**.

See [detailed Phase 2 checklist](phase2-plan.md) and [validation report](phase2-validation-report.md).

## Later phases (planned, not implemented)

- [ ] Phase 3: trusted worktree broker, durable state, budgets and gated approvals.
- [ ] Phase 4: cross-provider roles and measured routing.
- [ ] Phase 5: hardware domain validation and optional GPU worker.
- [ ] Phase 6: GitHub broker, installation/update/rollback and machine handover.
- [ ] Phase 7: held-out matched baseline evaluations and calibrated release.

## Exit status

Phase 0 complete. Phase 1 offline foundation complete on the observed macOS/Python environment. All ten procedures were exercised across invoice, independent-review and optimisation development cases. Review found two outcome contradictions; both were fixed and independently rechecked. Required browser/GPU/provider boundaries remain explicitly unverified and are later-phase gates, not Phase 1 passes. The external skill-creator validator was unavailable due to missing PyYAML; local pack checks passed.

Phase 2 implementation and authorized feasibility experiments are recorded. Both engines now pass the trusted disposable-workspace coding fixture on the tested macOS host. No merge, push, PR, global CLI edit, plugin installation, GPU connection, API-key introduction or billing change occurred in the follow-up. Phase 3 may begin only for that narrow mode; untrusted or broad local execution remains blocked.

Publication follow-up, 2026-09-19: the user subsequently authorized creating a private GitHub repository and pushing all committed toolkit branches. This supersedes the local-only publication restriction without changing the Phase 2 findings or granting PR/merge permission. See D025 in the [decision log](decisions.md).
