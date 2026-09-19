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

## Phase 3 — minimum durable delivery workflow

- [x] Verify exact `39afb7feac0bde09fc390b85c4d8c8db83bea0b3`, preserve the clean Phase 2 tree and create `implementation/phase-3` in a dedicated worktree.
- [x] Persist validated task transitions, append-only events, dependencies, revisions, executions, evidence and next actions transactionally in SQLite.
- [x] Keep controller authority out of worker data; worker output cannot change state, reserve budget or record approval.
- [x] Create one controller-owned repository, task branch and worktree; give the implementer a plain tracked-file copy without `.git` and apply only contract-allowed changes through the Git broker.
- [x] Bind verification, review and the local approval package to the candidate revision; revision changes stale prior evidence and approvals.
- [x] Integrate either existing provider adapter as implementer and the other as model-only reviewer; keep deterministic adapters as the default test path.
- [x] Enforce two repairs at most and stop repeated identical findings with a durable checkpoint.
- [x] Reserve calls, concurrency, timeout and elapsed allocations before launch; preserve unknown usage and distinct cached-token categories.
- [x] Reconcile active executions after restart as blocked when process ownership cannot be established; never launch a silent replacement.
- [x] Produce a local summary, diff, revisions, checks, review findings, limitations, resources and proposed PR text, ending at `awaiting_pr_approval` with no recorded approval.
- [x] Test illegal transitions, duplicate/immutable events, concurrent reservations, stale evidence/approval, authority forgery, repair limits, cancellation and restart reconciliation.
- [x] Complete and archive a deterministic disposable workflow through `awaiting_pr_approval`.
- [x] Attempt one bounded live cross-provider workflow: Codex implementation and independent test passed; Claude review failed closed on an expired OAuth token, with no approval package.
- [ ] Complete a live cross-provider workflow through review after the operator independently restores Claude subscription authentication.
- [ ] Crash-safe process containment, detached descendants and remote cancellation: **unsupported**.
- [ ] Broad repositories, hostile code, tool-network separation and comprehensive credential isolation: **blocked**.

## Phase 3 corrective review

- [x] Verify all five review findings against exact commit `17eba897c2cada2957642c36a4c5ddfb5d967a7b`; create `implementation/phase-3-review-fixes` in a separate worktree.
- [x] Attach controller-generated JSON feedback to repair prompts, including structured review findings or bounded failed-test output and acceptance criteria.
- [x] Prove feedback-dependent repair behavior for both failed verification and review findings.
- [x] Run independent tests from a controller-created copy with controller-owned test content under a read-only, no-network Seatbelt profile.
- [x] Scrub the verification environment, replace `HOME`, deny the invoking home plus controller, approval, evidence, repository and worktree paths, and compare both candidate and verification-copy manifests after execution.
- [x] Pass the host boundary regression with disposable controller, approval, Git, worktree and fake-credential canaries; never inspect real credential contents.
- [x] Bind implementer, repair, verification and reviewer reservations/starts to their valid task states; reject terminal and unresolved tasks.
- [x] Add explicit reconciliation resolution that releases the held reservation while leaving the uncertain task blocked.
- [x] Reject Boolean, nonnumeric, zero/negative where invalid, NaN and infinity in controller budget, timeout, elapsed and cost observations.
- [x] Namespace repair/failure event IDs by task and test two tasks with the same signature.
- [ ] Complete a new live cross-provider workflow: **still blocked/unverified because the retained Claude attempt ended with expired OAuth; no authentication change or live rerun was performed in this corrective pass**.

## Phase 3 authentication recovery

- [x] Start from exact `b7ce31826803f640330bd21f879523508d32c0ff` on `implementation/phase-3-auth-recovery` in a dedicated worktree.
- [x] Verify installed Codex and Claude Code login/status help against official provider documentation.
- [x] Support Codex browser/device login and Claude subscription browser login with its official manual code handoff.
- [x] Keep official login in an attached controller-side terminal; never capture its input, output, authorization codes or transcript.
- [x] Reuse working subscription auth and exclude API-key/provider override variables without logging out, moving or reading credential contents.
- [x] Persist a secret-free authentication checkpoint bound to provider, interrupted stage, failed execution, candidate revision and evidence references.
- [x] Coordinate one login per provider/account context, allow two attempts, and keep waiting outside model execution and repair accounting.
- [x] Resume only implementer, repair or reviewer state after subscription status, execution finality, candidate, evidence and reconciliation checks pass.
- [x] Test existing/missing/expired auth, successful stage resume, cancelled/failed/timed-out login, duplicate login, restart, uncertainty, stale evidence, non-auth failures, secret exclusion and accounting preservation.
- [x] Complete the bounded live Codex implementation → constrained verification → Claude review → local approval package demonstration without repeating a successful inference for evidence.
- [ ] Other platforms, remote terminal handoff, custom credential stores and complete login-process credential isolation: **unverified/unsupported**.

## Phase 3 authentication recovery corrective review

- [x] Start from exact `cc7d7587b6f282a8220df1cf159eb04b55314eea` on `implementation/phase-3-auth-recovery-fixes` in a dedicated worktree.
- [x] Replace the per-task checkpoint uniqueness constraint with historical checkpoints plus one active checkpoint per task; migrate schema v2 transactionally.
- [x] Exercise sequential Codex implementation and Claude review authentication failures, preserving both checkpoints and bounded attempts.
- [x] Persist login process ownership and require explicit still-running, confirmed-ended or uncertain reconciliation; never reclaim on elapsed time alone.
- [x] Handle Ctrl+C and launcher failure without starting a duplicate login, preserving uncertain termination when cleanup cannot be established.
- [x] Bind checkpoints to the controller-owned repository, worktree, branch, HEAD, clean status and file-manifest digest and recompute them before resume.
- [x] Reject a dirty candidate before restoring reviewer state or producing an approval package.
- [x] Preserve completed work, resource accounting, secret exclusion and the existing worker/verifier sandbox boundaries.
- [x] Run disposable fixture regressions only; spend no live inference quota.
- [ ] Interactive provider login recovery remains fixture-tested; the successful live delivery reused existing authentication and did not exercise browser login.

## Phase 4 — task intake and selective orchestration

- [x] Start from exact `fa288720c2f1c5e85b33e5ed8a00d88c240f1a77` on `implementation/phase-4` in a dedicated worktree.
- [x] Add a coherent `task` CLI for fixture discovery, intake, plan inspection, execution, status, cancellation, authentication resume and local package reading.
- [x] Preserve the original request separately from explicit assumptions; reject non-fixture targets and authority expansion.
- [x] Define chief-of-staff, tech-lead, manager, implementer, verifier and reviewer responsibilities without starting unnecessary management models.
- [x] Persist bounded graph nodes/edges and require acyclic dependencies, completed prerequisites, isolated specialist worktrees and controller-owned integration.
- [x] Route implementer/repair/reviewer through configurable Codex/Claude account-default profiles, preserving unknown model, effort, relative price and availability.
- [x] Protect separate verification and review call reserves; enforce calls, concurrency, elapsed allocation, timeout, subtasks, repairs, graph size and output bounds.
- [x] Hash and record only selected audited skill/domain content and use structured bounded handoffs instead of transcripts.
- [x] Preserve authentication checkpoints, candidate/evidence revalidation, cancellation and restart uncertainty behavior.
- [x] Test the minimal task path, decomposed integration, invalid graph/authority plans, routing, reserves, repairs, auth recovery, stale revisions, cancellation and unknown usage.
- [x] Include an adversarial worker fixture whose unauthorized file change is rejected by the broker.
- [x] Complete and archive one bounded Codex implementation → constrained verification → Claude review demonstration at the exact integrated candidate, with two inference calls and no repair.
- [ ] General repository onboarding, Linux/GPU workers, dashboards, GitHub publication and broad autonomous execution remain unsupported.

## Phase 4 corrective review

- [x] Start from exact `af807914dc39ef3f9527461ef97e888b860b494d` on `implementation/phase-4-review-fixes` in a dedicated worktree.
- [x] Align the live implementer cancellation interface and exercise actual adapter/request construction with only external transports stubbed.
- [x] Persist decomposed assignment identity before provider launch; validate and reuse it after authentication while preserving completed siblings.
- [x] Cover authentication failure in either text-metrics subtask and reject a changed assignment before restoring task state.
- [x] Propagate requested model and supported Claude effort through implementer, repair and reviewer paths; reject unsupported effort settings.
- [x] Separate requested configuration from nullable provider-reported configuration in execution status and evidence.
- [x] Rehash and assemble bounded role-relevant skill/domain contents into actual provider prompts; reject changed sources and omit unrelated skills.
- [x] Correct scope claims: decomposition is fixture-defined, execution is sequential, management roles are deterministic and routing is not calibrated optimization.
- [x] Preserve the prior live archive unchanged and label it historical evidence for `af80791` rather than validation of the corrected revision.
- [x] Complete the 137-test repository suite with status `OK` and one expected nested-Seatbelt skip, pass that boundary regression separately at host level and pass `agentkit check`.
- [ ] Run a new bounded live workflow for the corrected revision only under separate authorization; no live inference is spent in this corrective pass.

## Later phases (planned, not implemented)

- [ ] Phase 5: hardware domain validation and optional GPU worker.
- [ ] Phase 6: GitHub broker, installation/update/rollback and machine handover.
- [ ] Phase 7: held-out matched baseline evaluations and calibrated release.

## Project documentation

- [x] Reorganize the README as a public project landing page with an offline quick start, architecture, exact CLI scope, support matrix, validation evidence, contribution guidance and explicit license status.

## Exit status

Phase 0 complete. Phase 1 offline foundation complete on the observed macOS/Python environment. All ten procedures were exercised across invoice, independent-review and optimisation development cases. Review found two outcome contradictions; both were fixed and independently rechecked. Required browser/GPU/provider boundaries remain explicitly unverified and are later-phase gates, not Phase 1 passes. The external skill-creator validator was unavailable due to missing PyYAML; local pack checks passed.

Phase 2 implementation and authorized feasibility experiments are recorded. Both engines now pass the trusted disposable-workspace coding fixture on the tested macOS host. No merge, push, PR, global CLI edit, plugin installation, GPU connection, API-key introduction or billing change occurred in the follow-up. Phase 3 may begin only for that narrow mode; untrusted or broad local execution remains blocked.

Phase 3 now implements the minimum local delivery graph for that narrow mode. After the corrective review, the deterministic workflow reaches a revision-bound `awaiting_pr_approval` package and 91 tests cover controller, Git, repair feedback, constrained verification, budget, numeric, lifecycle, restart and evidence invariants. The bounded live attempt validated Codex implementation plus an independent test, then blocked when Claude reported an expired OAuth token. No reauthentication was attempted, no billing fact was inferred, and no live approval package was created. Phase 4 should wait for a successful cross-provider live review and remains limited to trusted controller-created disposable repositories.

The authentication-recovery follow-up supersedes that live gate: guided first-party subscription recovery is implemented and 107 tests pass, including the host macOS boundary test. One fresh bounded live workflow reached `awaiting_pr_approval` with Codex implementation, constrained local verification and Claude review. Existing authentication worked, so no interactive login was launched. A strict offline correction accepted Claude's single fenced JSON result after verifying its archived stream hash, provider-success terminal, candidate and snapshot, avoiding any repeat inference. Phase 4 may begin only for the same trusted disposable macOS mode; all broader limitations remain.

Phase 4 now provides fixture-only natural-language intake, a reviewable plan, selective persisted role graphs, configurable account-default provider routing, separate verification/review reserves, active cancellation and a terminal status/package experience. The final suite passed 131 tests with one nested-sandbox skip, and the host boundary regression passed separately. One live two-inference-call workflow reached a clean revision-bound local package. General repositories, additional platforms, GPU/remote workers, dashboards and publication remain future gates.

The Phase 4 corrective review fixes the live cancellation interface, decomposed authentication resume, requested model/effort propagation and verified worker skill context. The corrected revision completes its 137-test repository suite with status `OK` and one expected nested-Seatbelt skip; the skipped boundary test passes separately at host level. The earlier live package remains historical evidence for `af80791`. No live inference was used for the correction, so the corrected live implementation → verification → review path still needs one future bounded validation.

Publication follow-up, 2026-09-19: the user subsequently authorized creating a private GitHub repository and pushing all committed toolkit branches. This supersedes the local-only publication restriction without changing the Phase 2 findings or granting PR/merge permission. See D025 in the [decision log](decisions.md).
