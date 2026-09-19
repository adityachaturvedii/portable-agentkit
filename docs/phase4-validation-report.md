# Phase 4 validation report

Date: 2026-09-19

Corrective branch: `implementation/phase-4-review-fixes`

Corrective base: `af807914dc39ef3f9527461ef97e888b860b494d`

Corrected live validation branch: `validation/phase-4-corrected-live`

Tested executable revision: `342423ea27700e7d46a977d47e3307bd8fa58c23`

Concurrent increment branch: `implementation/phase-4-dynamic-scheduling`

Concurrent increment base: `41290944ca3a6048e0ed7c3eb85331d028f18a43`

Concurrent live-tested executable: `b22020cf6a1587617d14e8c6164581a5d291ed93`

Offline-corrected executable: `b9df1ad8af93f9d62124859b30246d971f273e83`

Dependency/claim/request correction: `dd8da0ed2eaf973a646bb5f2e95fcd543fddb3b9`

Static-web executable milestone: `70070e293c890a5c47bbb448b99a9b7cf34f8237`

## Bounded static-web product acceptance path

The product path accepts an arbitrary product brief only within a fixed fresh static-web inventory. One accounted Claude account-default tech-lead call proposes deliverables, dependencies, four-file write scopes, interfaces, observable criteria and allocations. The controller requires the proposal to preserve the original request and predeclared acceptance and rejects unsupported operations, stale inventory, unsafe paths, inconsistent summaries, cycles, fan-out above two, independent overlap and mandatory call/time excess. No game solution or game-specific assignment graph is present in the harness.

Validated assignments reuse the existing atomic scheduler and broker. The controller-created repository, assignment worktrees and worker copies are under the workflow managed root; controller state, evidence, approvals, Git metadata and mechanics-test source remain outside worker scope. The dependency-free profile permits no install or package-manager network access. It records the installed Node path/version/hash, copies that executable into the disposable verification runtime, runs `node --check game.js` plus controller-owned mechanics checks in a separate candidate copy, and requires the candidate manifest/revision to remain unchanged.

Passing mechanics and independent review stop at `review_complete`. Packaging requires a clean exact-revision browser evidence object covering every protected acceptance ID, browser identity, hashed screenshots where retained, explicit final visual judgment, and a recorded preview session with confirmed process cleanup. The supported preview stays in one foreground controller process until Ctrl+C and records cleanup in `finally`. Detached descendants, browser credential isolation, browser egress control and crash-safe process recovery are not claimed.

Nine focused product tests use deterministic planning/provider fixtures and one external-transport-only planner stub. They cover real model-only request construction, malicious scope/cycle/acceptance rejection, mandatory budget infeasibility, immutable product-spec binding, generated-project isolation, protected Node mechanics acceptance, unchanged-candidate evidence, stale candidate rejection, screenshot hash checking, browser gating and local package binding. The preview lifecycle test is skipped inside the managed outer sandbox because loopback `bind` returns `PermissionError`; it passes separately at host level with the foreground owner recording confirmed cleanup. After the output-allocation correction, the 167-test repository suite passes with the expected nested-Seatbelt and managed-loopback skips. No further live inference was used for this implementation evidence.

## Bounded Breakout trial

The trial tested exact executable `70070e293c890a5c47bbb448b99a9b7cf34f8237`. Read-only preflight reported Codex CLI 0.154.0 and Claude Code 2.1.220 using existing first-party subscription authentication. The controller recorded account-default Claude planning, Codex implementation and cross-provider Claude review routes; requested model and effort were `null`. The declared ceiling was eight provider calls, two simultaneous workers, two repairs, 180 seconds per provider call, 10 seconds per local verification and 1,200 seconds overall.

Only the planning invocation ran. It ended after 29.313421 seconds with no structured proposal. Claude Code's terminal message says the response exceeded the configured 512 output-token maximum. The stream also included an allowed rate-limit metadata event with overage disabled, causing the existing broad classifier to label the combined failure `rate_limit`; this is a classification defect. The direct terminal cause was the adapter's planner output allocation, not an observed subscription usage-limit or payment demand. The controller made no retry, provider substitution or authentication change.

The task remains `blocked` before contract/plan persistence, repository creation or candidate revision. Therefore no generated task graph, game, build, mechanics verification, review, repair, preview, browser check, screenshot or local approval package exists. This failed trial does not validate any subsequently corrected code.

The offline follow-up adds a durable Claude-only `max_generated_output_tokens` request field constrained to 256..8,192 and configures the product planner at 8,192. The ordinary model-only smoke retains 512, owned-code Claude retains its 2,048 default, and Codex rejects this unsupported setting. Error classification now recognizes the terminal output-limit text before allowed rate metadata. Fixture tests cover request validation, actual transport environment propagation and the archived failure string. No second provider call was made, so this correction remains live-unvalidated.

Claude reported 8 input, 2,048 output, 25,570 cached-input and 9,678 cache-creation tokens. Reasoning tokens are unknown. It reported a USD 0.160805 estimate; billed cost and account billing impact are unknown. The [trial archive](../evidence/phase4-webgame-trial/manifest.json) retains the brief, protected criteria/test, request hash, redacted stream, normalized result, controller snapshot, status, versions, usage and diagnosis without the SQLite database, credentials, login transcripts, authorization codes or environment values.

## Request-driven planning and concurrency increment

This increment keeps the supported target at trusted controller-created disposable projects on the tested macOS profile. It adds request/inventory-bound planning, request-selected protected acceptance, ordered and independent assignment graphs, a real two-worker scheduler, durable owner records, conservative controller integration, explicit routing policies and separate provider/planning-call budgets. Routine planning remains deterministic. Contradictory requirements stop for clarification, and unaccounted model-assisted planning is rejected.

### Post-review dependency, claim and request correction

The follow-up review found that ordered nodes launched in the correct order but still forked from the task base, a stale in-memory selection could exploit the generic success-to-running transition, and an unmatched request selected every predefined fixture subtask. The correction composes a dependent worker's start from validated predecessor-owned deltas, records the actual starting revision and dependency provenance, measures only the worker's own delta, and integrates those deltas once in stable graph order. Independent overlaps, invalid ancestry and stale dependency identities block explicitly.

Implementation claims now use one `BEGIN IMMEDIATE` compare-and-set over the selected status, update timestamp and attempt count while rechecking dependencies, cancellation and ownership. A stale contender receives no claim and cannot launch or overwrite success. Quality retries reset through an explicit pending state; generic success-to-running is invalid. The deterministic planner now raises an unsupported result on a term miss and requires clarification for negated or contradictory matched work.

Focused tests include runtime-generated predecessor content that the downstream worker must read, a synchronized stale-selection contender released only after the winner commits, and supported/unmatched/negated/contradictory request cases. These corrections use deterministic providers and disposable repositories only; no live inference or historical evidence mutation is involved.

Sixteen focused behavioral tests cover different request plans, a one-assignment plan without management calls, clarification, adversarial plan rejection, barrier-proven two-worker overlap, ordered dependency launch, duplicate-controller suppression, integration conflict preservation, sibling completion during authentication failure, cancellation observed by both workers, uncertain owner blocking, dated routing configuration, cross-contributor review independence, time-budget infeasibility and bounded repair/model escalation. One test drives the actual scheduler and `LiveImplementer`/`LiveReviewer` request construction while stubbing only external provider transports; it verifies concurrent requests, exact model/effort and configured 7/8-second request limits.

Before live execution, `python3 -m unittest discover -s tests -v` passed 153 tests with one expected nested-Seatbelt skip in the managed session. After the shell-runtime correction described below, it passed 154 tests with the same expected skip. `python3 -m agentkit check` passed the offline 10-skill, 7-domain, 10-example and 3-source inventory. The prior corrected calculator archive remains evidence for executable `342423e`; it does not validate concurrent scheduling.

## Concurrent live attempt and narrow correction

The authorized run tested exact executable `b22020cf6a1587617d14e8c6164581a5d291ed93` on the supported macOS host with Codex 0.154.0 and Claude Code 2.1.220. Both official status commands reported existing subscription authentication. The disposable `text-metrics` contract used deterministic planning, Codex account-default implementation profiles and a Claude account-default review profile; every requested and provider-reported model/effort value remained `null`. The controller enforced four total calls, three provider calls, two concurrent workers, two 60-second implementation allocations, one 10-second verification allocation, one 60-second review allocation, 190 allocated seconds, 1 MiB output per call and zero repairs, retries or escalations.

The two Codex implementation calls started 0.082272 seconds apart and overlapped for 43.367214 seconds. The word worker completed in 55.040581 seconds, changed only `words.py`, and the broker committed assignment revision `ff44028cbf39740671a845224a8e6d8b55f69b85`. The line worker completed in 43.012412 seconds but changed no file, so the broker rejected it with `authority_violation: worker produced no changes`. The controller blocked with the integrated worktree clean and unchanged at base `dd2b246a1136c412b6ff59f698e8468b4c87b389`. Integration, local verification and Claude review did not run. No repair, retry, escalation, provider substitution, approval package or publication approval occurred.

The retained redacted stream shows the specific boundary failure. Git could not open the configured `GIT_CONFIG_GLOBAL=/dev/null` sink, and zsh could not create a heredoc temporary file because it uses `TMPPREFIX`, which had not been placed inside the allowed runtime. A later empty unittest-discovery command returned success, so the provider turn itself completed even though `lines.py` remained unchanged. The broker and controller therefore failed closed at the independent filesystem result boundary.

The two calls reported 101,996 input, 1,920 output, 84,352 cached-input and 149 reasoning tokens in total. Cache-creation tokens, estimated cost and billed cost are unknown. Provider elapsed time sums to 98.052993 seconds; the concurrent wall interval was 55.387876 seconds. These are provider observations, not billing. The controller launched exactly two provider executions; provider-managed hidden transport retries remain unknown.

Revision `b9df1ad8af93f9d62124859b30246d971f273e83` applies the narrow correction: set zsh `TMPPREFIX` under the already allowed per-execution runtime and permit writes only to the literal `/dev/null` device. A real adapter-boundary regression stubs only external process transport, and a disposable no-inference host canary verified heredoc creation and `git status` while a protected write remained denied. The full 154-test suite and structural check pass. No further inference was run, so `b9df1ad` is offline-validated and still needs a separate bounded concurrent live completion before that path can be called live-tested.

The [concurrent live-attempt archive](../evidence/phase4-concurrent-live/manifest.json) retains CLI/auth preflight, exact revisions, contract, plan, registry, sanitized requests, redacted provider events, results, controller state, assignment identities, the successful contribution diff, usage, failure diagnosis and correction canary. It excludes the controller database, credentials, authorization codes, raw login transcripts and environment values.

## Corrected single-assignment baseline implemented and independently tested

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

Most provider outcomes, authentication expiry/recovery, quota-independent failures, review findings and repairs use deterministic adapters. The concurrent increment's adapter/request construction is exercised with only external execution transports stubbed. Synchronization primitives prove controller overlap without inference. Chief-of-staff, tech-lead and manager labels remain deterministic controller responsibilities rather than autonomous reasoning. Routing follows configured evidence and defaults; calibrated model optimization is not claimed. Interactive browser/device login remains fixture-tested.

## Corrected live validation

One fresh calculator workflow tested executable commit `342423ea27700e7d46a977d47e3307bd8fa58c23` on macOS 26.6.2 arm64 with Python 3.9.6, Codex 0.154.0 and Claude Code 2.1.220. Both official status commands reported existing first-party subscription authentication; no login flow ran. The contract requested the Codex and Claude account defaults with `model=null` and `effort=null`. The controller allowed exactly three calls, one concurrent execution and 130 allocated seconds: one 60-second Codex implementation, one 10-second constrained verification and one 60-second Claude review. The quality reserves left no capacity for repair inference, provider substitution or another review.

The workflow used two inference executions and one local verification execution, with zero repairs. Codex changed only `calculator.py`. The controller committed candidate `ee3f6ffc260f6cf1ee5537db1913debb0f4168ff`; its worktree was clean and its diff changed `return left - right` to `return left + right`. The independent read-only/no-network verifier passed its controller-owned acceptance at that exact revision and recorded `candidate_unchanged=true`. Claude reviewed the same revision, returned the strict `no_findings` object and used no tools or MCP servers. The task reached `awaiting_pr_approval`; the package binds the base, candidate, diff, passing verification and review, while the approval table remains empty.

The reconstructed 4,959-byte implementation prompt and 5,873-byte review prompt match the hashes and byte counts captured before launch. The implementer prompt contains only its assignment, behavioral-testing procedure and backend/database domain context. The reviewer prompt contains the immutable candidate, contract, independent-review procedure and the same domain context. Requested configuration remains separate from provider-reported configuration: Codex reported no model or effort, while Claude reported `claude-opus-5[1m]` and no effort.

Controller-observed elapsed time was 56.668539833 seconds: Codex 52.578902, verification 0.349434833 and Claude 3.740203. Codex reported 76,320 input, 900 output, 63,360 cached-input and 0 reasoning tokens; cache-creation tokens and estimated/billed cost were unknown. Claude reported 2 input, 176 output, 0 cached-input and 4,644 cache-creation tokens; reasoning was unknown. Claude emitted a USD 0.05085 estimate; billed cost remained unknown. Cross-provider totals stay unreported where any contributing category is unknown, and the estimate is not billing.

The committed [corrected live archive](../evidence/phase4-corrected-live/manifest.json) contains sanitized request records, exact hash-matched prompts, redacted provider events, results, controller state/events/artifacts, verification, candidate identity/diff and the approval package. Its manifest binds 28 files to the tested executable and candidate revisions. No credential, authorization code, raw login transcript or sensitive environment value is included. Codex emitted no reported reconnect or retry, but its built-in subscription transport still cannot be configured to prove zero hidden native retries; the controller launched exactly the two authorized provider executions.

## Historical live evidence

The archived calculator demonstration was produced by Phase 4 commit `af807914dc39ef3f9527461ef97e888b860b494d` and reached `awaiting_pr_approval` at disposable candidate `6c3074a5ee12a2577cf20fd7a2a45c0a8f638b73`. Its declared budget was five calls, one concurrent execution, 180 allocated seconds, 60 seconds per provider call and 1 MiB output per call. It completed one Codex implementation, one constrained local verification and one Claude review in 42.260266291 seconds. Verification passed at that candidate, Claude reported no material finding, no repair or authentication flow ran, two calls remained, and no approval/publication was recorded.

Codex reported 47,785 input, 600 output, 37,120 cached-input and 0 reasoning tokens. Claude reported 2 input, 304 output, 0 cached-input and 3,007 cache-creation tokens; reasoning was unknown. Claude emitted a USD 0.03768 estimate. Codex estimated cost and all billed-cost values were unknown. The aggregate categories remain unknown because unavailable fields are not converted to zero, and the Claude estimate is not billing.

The sanitized contract, plan, registry, status, package and summary are SHA-256 bound by `evidence/phase4/manifest.json`. Raw provider streams were not added to this Phase 4 archive. Because that run predates the adapter/interface correction, it remains historical evidence only. The corrected live validation above supersedes its outstanding validation gate without rewriting or promoting the older evidence.

## Unsupported behavior

General or personal repositories, Linux/Windows/GPU/remote execution, dashboards, detached-process containment, remote cancellation, tool-network separation, comprehensive credential isolation, exact model inventory, exact token/dollar caps, API-key or paid fallback, GitHub publication, merge and deployment are unsupported. The controller supports the previously tested trusted controller-created disposable macOS execution mode only.
