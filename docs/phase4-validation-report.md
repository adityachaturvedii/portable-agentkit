# Phase 4 validation report

Date: 2026-09-19

Corrective branch: `implementation/phase-4-review-fixes`

Corrective base: `af807914dc39ef3f9527461ef97e888b860b494d`

## Implemented and independently tested

- Task intake preserves the original request and explicit assumptions, validates the supported fixture/profile and rejects unsupported targets.
- The terminal interface submits, inspects, starts, reports, cancels, resumes supported authentication checkpoints and reads a local approval package.
- Role and graph contracts bound nodes, dependencies, paths, fan-out, attempts and repair loops. Persisted dependencies gate launch.
- The single calculator path avoids management calls. Fixture-defined decomposition uses two specialist branches/worktrees sequentially and one controller-owned integration commit.
- A decomposed assignment identity is persisted before provider launch, validated before authentication resume and safely reused; completed sibling work is preserved.
- Configurable Codex/Claude routing propagates requested model and supported Claude effort through the live adapters while keeping provider-reported values separate and nullable.
- Separate verification and review call reserves survive implementation pressure. Output is bounded; unavailable usage and cost stay unknown.
- Role-relevant audited skill/domain content is rehashed and assembled into bounded provider context. Repair also receives bounded controller-generated failed-test or structured-review feedback.
- Adversarial scope expansion is rejected without changing the parent candidate or producing a package.
- Cancellation prevents launches, uncertain restart state blocks replacement, authentication resume preserves completed work and budgets, and a changed actual worktree rejects resume before packaging.
- Packages bind the integrated revision, separate resolved from active findings and record no publication approval.

The original Phase 4 review passed 17 Phase 4 tests and 22 authentication tests before reproducing the defects corrected here. The corrective suite adds real live-adapter request construction with stubbed external transports, decomposed authentication failures in either subtask, changed assignment identity, implementer/repair/reviewer model propagation, supported effort validation, role-specific context assembly and changed-skill rejection. `python3 -m unittest discover -s tests -v` completed its 137-test suite with status `OK` and one expected nested-Seatbelt skip in the managed session. The skipped macOS boundary regression passed separately at host level. `python3 -m agentkit check` also passed all offline structural checks for 10 skills, 7 domains, 10 examples and 3 pinned sources.

## Simulated behavior

Most provider outcomes, authentication expiry/recovery, quota-independent failures, review findings and repairs use deterministic adapters. Live adapter/request construction is exercised with only the external execution transports stubbed. The current controller executes fixture-defined specialist nodes sequentially, so concurrent scheduling is not claimed. Chief-of-staff, tech-lead and manager labels describe deterministic controller responsibilities rather than autonomous reasoning. Routing follows configured evidence and defaults; calibrated model optimization is not claimed. Interactive browser/device login remains fixture-tested.

## Historical live evidence

The archived calculator demonstration was produced by Phase 4 commit `af807914dc39ef3f9527461ef97e888b860b494d` and reached `awaiting_pr_approval` at disposable candidate `6c3074a5ee12a2577cf20fd7a2a45c0a8f638b73`. Its declared budget was five calls, one concurrent execution, 180 allocated seconds, 60 seconds per provider call and 1 MiB output per call. It completed one Codex implementation, one constrained local verification and one Claude review in 42.260266291 seconds. Verification passed at that candidate, Claude reported no material finding, no repair or authentication flow ran, two calls remained, and no approval/publication was recorded.

Codex reported 47,785 input, 600 output, 37,120 cached-input and 0 reasoning tokens. Claude reported 2 input, 304 output, 0 cached-input and 3,007 cache-creation tokens; reasoning was unknown. Claude emitted a USD 0.03768 estimate. Codex estimated cost and all billed-cost values were unknown. The aggregate categories remain unknown because unavailable fields are not converted to zero, and the Claude estimate is not billing.

The sanitized contract, plan, registry, status, package and summary are SHA-256 bound by `evidence/phase4/manifest.json`. Raw provider streams were not added to this Phase 4 archive. Because that run predates the adapter/interface correction, it is historical evidence only and does not validate the corrected final revision. No live inference was used for this corrective pass. A separate bounded live implementation → verification → review run remains needed to validate the corrected live path.

## Unsupported behavior

General or personal repositories, Linux/Windows/GPU/remote execution, dashboards, detached-process containment, remote cancellation, tool-network separation, comprehensive credential isolation, exact model inventory, exact token/dollar caps, API-key or paid fallback, GitHub publication, merge and deployment are unsupported. The controller supports the previously tested trusted controller-created disposable macOS execution mode only.
