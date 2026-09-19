# Phase 4 validation report

Date: 2026-09-19

Branch: `implementation/phase-4`

Base: `fa288720c2f1c5e85b33e5ed8a00d88c240f1a77`

## Implemented and independently tested

- Task intake preserves the original request and explicit assumptions, validates the supported fixture/profile and rejects unsupported targets.
- The terminal interface submits, inspects, starts, reports, cancels, resumes supported authentication checkpoints and reads a local approval package.
- Role and graph contracts bound nodes, dependencies, paths, fan-out, attempts and repair loops. Persisted dependencies gate launch.
- The single calculator path avoids management calls. The decomposed text-metrics path uses two specialist branches/worktrees and one controller-owned integration commit.
- Configurable Codex/Claude account-default routing records provider, nullable model/effort, unknown relative cost and its reason. Material decomposed work requires cross-provider review.
- Separate verification and review call reserves survive implementation pressure. Output is bounded; unavailable usage and cost stay unknown.
- Selected audited context is content-hashed. Repair receives bounded controller-generated failed-test or structured-review feedback.
- Adversarial scope expansion is rejected without changing the parent candidate or producing a package.
- Cancellation prevents launches, uncertain restart state blocks replacement, authentication resume preserves completed work and budgets, and a changed actual worktree rejects resume before packaging.
- Packages bind the integrated revision, separate resolved from active findings and record no publication approval.

The Phase 4 behavioral module contains 17 tests, including hash-bound live evidence, active cancellation and reviewer-stage authentication resume. The final complete repository suite passed 131 tests with one expected nested-sandbox skip; the host-specific Seatbelt boundary regression passed separately outside that nested context. The offline pack check and `git diff --check` passed.

## Simulated behavior

Most provider outcomes, authentication expiry/recovery, quota-independent failures, review findings and repairs use deterministic adapters. Parallel readiness is represented by independent branches/worktrees and a concurrency-safe budget ledger; the current controller executes the two fixture specialists sequentially, so simultaneous provider processes are not claimed. Interactive browser/device login remains fixture-tested, consistent with the authentication recovery report.

## Live evidence

The live calculator demonstration reached `awaiting_pr_approval` at head `6c3074a5ee12a2577cf20fd7a2a45c0a8f638b73`. Its declared budget was five calls, one concurrent execution, 180 allocated seconds, 60 seconds per provider call and 1 MiB output per call. It completed one Codex implementation, one constrained local verification and one Claude review in 42.260266291 seconds. Verification passed at that exact head, Claude reported no material finding, no repair or authentication flow ran, two calls remained, and no approval/publication was recorded.

Codex reported 47,785 input, 600 output, 37,120 cached-input and 0 reasoning tokens. Claude reported 2 input, 304 output, 0 cached-input and 3,007 cache-creation tokens; reasoning was unknown. Claude emitted a USD 0.03768 estimate. Codex estimated cost and all billed-cost values were unknown. The aggregate categories remain unknown because unavailable fields are not converted to zero, and the Claude estimate is not billing.

The sanitized contract, plan, registry, status, package and summary are SHA-256 bound by `evidence/phase4/manifest.json`. Raw provider streams were not added to this Phase 4 archive. The live run reused working subscription authentication and did not test the interactive browser/device recovery path.

## Unsupported behavior

General or personal repositories, Linux/Windows/GPU/remote execution, dashboards, detached-process containment, remote cancellation, tool-network separation, comprehensive credential isolation, exact model inventory, exact token/dollar caps, API-key or paid fallback, GitHub publication, merge and deployment are unsupported. The controller supports the previously tested trusted controller-created disposable macOS execution mode only.
