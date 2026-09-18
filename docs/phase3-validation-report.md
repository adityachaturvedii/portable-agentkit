# Phase 3 validation report

Date: 2026-09-19 (Australia/Melbourne)

## Scope and starting point

Phase 3 started from verified commit `39afb7feac0bde09fc390b85c4d8c8db83bea0b3` in a new `implementation/phase-3` worktree. The implementation is limited to trusted controller-created disposable repositories on the macOS execution profile validated in Phase 2. It does not open personal repositories, publish to GitHub, connect to a GPU worker, change CLI authentication or billing, or install dependencies.

The delivered vertical path is:

`task intake -> validated contract -> controller-owned branch/worktree -> isolated worker copy -> brokered commit -> independent unittest -> revision-bound review -> bounded repair -> local approval package`

## Implemented capabilities

The controller persists tasks, dependencies, engine/model assignments, revisions, active executions, evidence and next actions in SQLite. State changes and budget reservations use immediate transactions. Events are append-only at the database layer: update and delete triggers abort, and event IDs are unique. A private in-process capability guards state changes, reservations and approvals; serialized worker data cannot recreate it.

The Git broker creates a disposable repository and one task branch/worktree. The implementer receives a plain copy of tracked files without `.git`. The broker rejects symlinks, additions, removals, renames and changes outside the contract path before copying an allowed change into the real worktree and committing it. Verification and review records name the candidate commit. A new head marks older evidence and approvals stale.

Budgets reserve capacity before launch and enforce calls, concurrency, elapsed allocation and per-execution timeout. Two call slots remain reserved for verification. Usage records preserve separate input, output, cached-input, cache-creation and reasoning counters; absent values and billed cost remain unknown. At most two repair cycles are allowed, and a second identical failure signature blocks the task with a durable checkpoint.

Restart reconciliation marks any reserved/running/cancellation-requested execution `reconciliation_required` and blocks its task. It does not launch a replacement or claim that the old process ended. Local approvals bind repository, branch, head, action and expiry. The demonstrated workflow stops before approval: its package says `approval.recorded=false`, and the approval table is empty.

## Independent validation

The offline suite passes 85 tests. Phase 3 cases cover illegal transitions, duplicate and immutable events, dependency readiness, concurrent call and elapsed-time reservations, verification reserve, nullable usage, cancellation, restart reconciliation, stale evidence, stale approval, authority forgery, Git boundary violations, review snapshot mutation, concrete finding validation, one repair, repeated failures, repair exhaustion, approval-package binding and archived evidence hashes. The repository pack check and whitespace check also pass.

The archived deterministic demonstration reached `awaiting_pr_approval`. Its independent unittest passed at candidate revision `eb94e4b8091aba4eb8154b4ee933c1917424f108`, the fake reviewer reported no finding, three execution allocations completed, and no approval was recorded. Provider decisions and usage in this run are simulated; the Git commits, controller persistence, manifest checks, unittest and package generation are real local operations. See [simulated evidence](../evidence/phase3/simulated-complete/summary.json).

## Bounded live attempt

One authorized cross-provider attempt used the existing subscription-authenticated CLIs. Codex implemented the disposable change under the Phase 2 owned-code profile. The broker accepted only `calculator.py`, committed revision `6ce4151a4dd6bdf90f0969387272bf19fef471de`, and the immutable unittest passed independently.

Claude review then returned `authentication`: its existing OAuth token had expired. The controller recorded the failed revision-bound review, transitioned the task to `blocked`, kept usage unknown for that execution and created no approval package. No reauthentication, API key, billing change, provider fallback or repeat inference was attempted. There was no usage-limit or payment-required signal. See [partial live evidence](../evidence/phase3/live-partial/summary.json).

Observed live resources were:

| Execution | Result | Elapsed | Provider usage observation |
|---|---|---:|---|
| Codex implementer | succeeded | 24.892412 s | 36,983 input; 34,688 cached input; 183 output; 0 reasoning |
| Local unittest | succeeded | 0.226971125 s | token usage unavailable |
| Claude reviewer | authentication failure | 1.037567 s | all token fields unavailable |
| Controller total | blocked after 3 completed allocations | 26.156950125 s | billed and estimated cost unavailable |

These are provider-reported token observations, not invoice or billing measurements. Cached input is a category within the reported input observation and is not added again to form a larger total.

## Effective boundaries

For implementation, the worker-visible filesystem is a disposable tracked-file copy. The configured Seatbelt boundary permits writes only to that copy and provider runtime/startup paths, and denies the controller database, approval directory, actual Git worktree and shared repository metadata. The broker independently checks the complete file manifest and contract scope. Phase 2 canaries established denial for named sibling, controller, fake-credential and Git paths under this execution profile; the Phase 3 live task reused that profile rather than probing secrets again.

The reviewer receives an embedded candidate snapshot bound to a commit and runs in model-only mode with tools disabled and an empty disposable working directory. A before/after manifest rejects any reviewer-side snapshot mutation. This establishes read-only behavior at the adapter and workflow boundary; it is not comprehensive OS credential isolation.

Provider traffic and any tool traffic would share the parent network boundary, so tool-network separation is unsupported. Parent CLI processes retain the subscription credential access needed for inference. Real credential contents were never probed. Comprehensive credential-path denial, hostile code, broad local repositories, non-macOS profiles, detached descendants, remote cancellation and crash-safe process containment remain unsupported. A restarted controller blocks uncertain executions for reconciliation.

## Demonstration

Run the deterministic workflow from a clean checkout with a fresh output path:

```sh
python3 -m agentkit controller-demo --output /tmp/agentkit-phase3-demo
```

The expected terminal state is `awaiting_pr_approval`. Inspect `/tmp/agentkit-phase3-demo/approval/approval-package.md`; the command does not record approval or publish anything. Live mode exists only for an explicitly authorized bounded subscription smoke and is not part of ordinary tests.

## Recommendation

The deterministic local workflow is ready for continued controller development on trusted disposable repositories. Phase 3 has enough evidence for local task, Git, verification, review, repair, budget, restart and approval-package semantics.

Full Phase 4 orchestration should not begin yet. First restore Claude subscription authentication outside this toolkit and complete one bounded cross-provider review through `awaiting_pr_approval`. That does not expand the security scope: broad repositories, hostile inputs, other platforms, detached-process containment, remote cancellation and tool-network or comprehensive credential isolation remain blocked until separately validated.

## Authentication-recovery follow-up — 2026-09-19

This follow-up supersedes the recommendation immediately above.

The follow-up starts from `b7ce31826803f640330bd21f879523508d32c0ff`. It adds official Codex browser/device login and Claude subscription browser/manual-code handoff, secret-free durable authentication checkpoints, provider/account login coordination, bounded attempts and exact-stage resume. Login is a separate attached terminal operation: its streams are never captured or persisted. See [authentication recovery](authentication-recovery.md).

The earlier partial run could not be resumed because only exported redacted evidence survived and its task was terminal `blocked`; no controller database or authentication checkpoint was available. One fresh live disposable run was therefore required. Codex implemented the same fixture, the constrained independent test passed, and Claude produced a provider-success no-findings review under existing first-party subscription authentication. No interactive login was needed.

Claude returned the valid review object inside one exact `json` Markdown fence. The strict adapter originally rejected it and moved the task to `blocked`. A regression-tested parser now accepts either a bare object or one exact JSON fence while continuing to reject prefixes, suffixes, wrong fence labels, duplicate keys, nonfinite values and non-objects. The retained live result was recovered offline without another inference call: the recovery verified the saved stream hash, a single provider-success terminal, the unchanged candidate revision, a snapshot identical to the reviewed copy and the concrete review schema before recording passing review evidence. The task then reached `awaiting_pr_approval`; no approval was recorded.

Observed live resources were:

| Execution | Controller result | Elapsed | Provider observation |
|---|---|---:|---|
| Codex implementer | succeeded | 25.945640 s | 37,016 input; 27,008 cached input; 203 output; 0 reasoning |
| Constrained local verification | succeeded | 0.243396 s | token usage unavailable |
| Claude reviewer | provider succeeded; controller format classification recovered offline | 3.231806 s | 2 input; 0 cached input; 2,831 cache creation; 139 output; reasoning unavailable; CLI estimate USD 0.031795 |
| Controller total | `awaiting_pr_approval` after 3 allocations | 29.420842 s | billed cost unknown |

The Claude dollar field is the CLI's estimate, not a billing measurement. Cached and cache-creation categories remain separate and are not added to input totals. Evidence is archived under [phase3-auth-recovery](../evidence/phase3-auth-recovery/manifest.json).

The bounded cross-provider gate for trusted controller-created disposable macOS workspaces is now satisfied. Phase 3 authentication recovery is ready for this same scope. Phase 4 may begin only within that scope; other platforms, untrusted repositories, remote login, detached-process containment, remote cancellation, tool-network separation and comprehensive credential isolation remain unsupported or unverified.
