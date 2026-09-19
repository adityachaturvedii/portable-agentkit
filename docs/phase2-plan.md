# Phase 2 implementation checklist and intake

Verified starting revision: 72a3ccd932e7b3517183176a4078dd8c754e8e4f. Phase 0–1 worktree was clean; 29 tests, package check and full range whitespace check passed before new worktree creation. No material Phase 1 defect found in this inspection; its lack of execution controls is explicitly scoped.

Dedicated branch: implementation/phase-2. No merge, push or PR. Python standard library only.

- [x] Inspect prior checklist, decisions, validation and implementation; reproduce checks.
- [x] Create dedicated worktree from exact verified revision.
- [x] Read-only doctor, version/feature/auth and sandbox availability observations.
- [x] Versioned provider-neutral request/result/usage/cancellation records.
- [x] Separate Codex/Claude adapters; bounded process/event handling, redaction and no controller retry/fallback.
- [x] Simulated provider success/error/timeout/cancel/child cleanup fixtures.
- [x] Disposable native sandbox canary tests and effective boundary matrix.
- [x] Existing-subscription preflight and bounded smoke attempts, with concrete blocked evidence for Codex.
- [x] Final verification, limitations, phase-3 recommendation and decisions.
- [ ] Full Phase 2 live-success exit criterion: Codex remains blocked; Claude correction tested by offline replay only.
- [ ] General tool and credential isolation: unsupported pending further architecture and boundary validation.

## Execution follow-up

The original entries above describe revision `6bfb981`. The follow-up on branch `implementation/phase-2-execution` completed both engines' disposable coding fixtures under a new external Seatbelt mode. Codex's startup requirement was narrowed to literal `~/.codex/installation_id`; Claude's transient state was narrowed to one preselected session path plus disposable temp storage. The complete findings and revised Phase 3 gate are in [phase2-execution-followup.md](phase2-execution-followup.md).

- [x] Both engines read, edited and tested a disposable fixture; independent acceptance passed.
- [x] Sibling workspace, fake credentials and controller state denied for reads and writes by the exact outer profile.
- [x] Timeout/cancellation and same-group TERM-resistant child cleanup passed offline.
- [ ] General tool network, credential and hostile-input isolation remains unsupported.

Safety boundary: no real secret-content probes, global settings edits, plugin install, GPU or billing changes. Auth status via official CLI only; never extract credentials. Native sandbox presence is distinct from effective initialization. macOS sandbox initialization fails when nested in the current agent sandbox, and succeeds in a separately authorized no-write probe. Claude status in the enclosing sandbox reports unauthenticated; read-only/no-network status outside it reports an existing first-party Max subscription. Neither login status establishes paid-overflow state.

Authorization chronology: the user initially answered unknown and blocked live inference, then explicitly authorized small existing-subscription smoke tests with no further billing investigation, no billing/auth changes, and stop-on-limit behavior. The later instruction superseded the temporary hold. One Claude task returned the correct synthetic result; Codex's guarded startup failed. No alternative provider or relaxed sandbox was tried. See [validation report](phase2-validation-report.md) for original records, parser correction and nullable usage.
