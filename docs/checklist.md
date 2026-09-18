# Implementation checklist

## Phase 0

- [x] Read and preserve the supplied implementation specification.
- [x] Create a fresh repository, dedicated branch and linked worktree; no remote.
- [x] Pin all three candidate skill repositories to full commits and archive hashes.
- [x] Inspect candidate files, referenced procedures, licenses, manifests and install surfaces.
- [x] Record per-file hashes and adopt/adapt/reject decisions; retain MIT notices.
- [x] Define Phase 1 requirements and threat model; distinguish future enforcement.

## Phase 1

- [ ] Ten portable core skills with narrow triggers, prerequisites, outputs and stop conditions.
- [ ] Seven initial domain procedures, loaded only when relevant.
- [ ] Structured, versioned JSON handoffs and fail-closed offline validation.
- [ ] Offline catalog, explicit intent selection, skill rendering and package checks.
- [ ] Disposable synthetic tasks, negative contract cases and independent forward evaluation.
- [ ] Document adaptations, tested platform, limitations and local PR proposal.

## Later phases (planned, not implemented)

- [ ] Phase 2: doctor, authenticated CLI adapters, canary-secret isolation, cancellation.
- [ ] Phase 3: trusted worktree broker, durable state, budgets and gated approvals.
- [ ] Phase 4: cross-provider roles and measured routing.
- [ ] Phase 5: hardware domain validation and optional GPU worker.
- [ ] Phase 6: GitHub broker, installation/update/rollback and machine handover.
- [ ] Phase 7: held-out matched baseline evaluations and calibrated release.
