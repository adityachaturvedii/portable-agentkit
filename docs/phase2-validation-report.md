# Phase 2 validation and disposition

Date: 2026-09-18. Dedicated worktree `portable-agentkit-phase02`, branch `implementation/phase-2`, exact base `72a3ccd932e7b3517183176a4078dd8c754e8e4f`. The Phase 0–1 tree was clean, and its 29 tests, package check and revision-range whitespace check passed before implementation. Its checklist, decisions, validation, archived evaluation and code were inspected; no material foundation defect was found. Its deferred provider/security controls were not misrepresented as implemented. The optional external validator remains unavailable without PyYAML; no dependency was installed.

## Implemented, simulated, unverified

| Capability | Disposition |
|---|---|
| Read-only doctor | Implemented; actual CLI versions/help/subscription status and native initialization observed. Credential contents/account identifiers never emitted. Unknown billing/overflow remains unknown. |
| Provider-neutral v1 records and separate adapters | Implemented; strict bounded requests, typed normalized results, nullable usage, provider details, redacted raw streams and artifact hashes. No SDK dependency. |
| Bounded noninteractive process lifecycle | Implemented and exercised through disposable executable fixtures: success, invalid/truncated/duplicate output, UTF-8 errors, missing executable, auth/rate/usage limits, timeout, cancellation, TERM-resistant children, orphan cleanup and output bounds. |
| Managed controls | Implemented: default deny, trusted explicit smoke authorization, exact CLI compatibility gate, subscription-only preflight, isolated empty cwd, write guard, scrubbed environment, no controller retry/provider fallback; unsupported modes block visibly. |
| Failure behavior | Provider failures simulated to avoid consuming quota. Native adverse provider behavior, hidden request counts, controller crash/restart, detached-descendant and remote cancellation remain unverified. |
| Sandbox feasibility | Real fake-secret/filesystem/loopback/process canaries, including symlink and common Git metadata cases; important negative credential findings retained. See matrix. |
| Live Claude | One actual subscription call completed the fixture. Original controller record has a classifier false positive; corrected parsing and acceptance verified by offline replay of the same captured events, with no new live call. |
| Live Codex | Initial invocation rejected invalid built-in retry overrides before inference. Corrected authorized attempt failed initializing the in-process app-server under the write guard. No inference output or usage observed. Successful live Codex completion remains unverified. |
| Full delivery hierarchy, scheduler, GPU, GitHub publication, transactional approvals/state | Planned only; not implemented or contacted. |

## Checks and reproducibility

Final result: **60 tests passed**, package check passed (10 skills, 7 domains, 10 examples, 3 source pins), and whitespace check passed. Run `python3 -m unittest discover -s tests -v` and `python3 -m agentkit check`. Tests are offline and include relocation with an empty HOME. [Final unittest log](../evidence/phase2/tests.txt), [pack check](../evidence/phase2/pack-check.json), and [evidence hash manifest](../evidence/phase2/manifest.json) retain the results. [Runtime contracts](runtime-contracts.md) define supported behavior. Live failure transcripts are immutable; later interpretations are separate records or tests.

`python3 -m agentkit doctor` performs no inference. Its no-global-write/no-network status guard may be unavailable inside an enclosing sandbox. It reports that limitation, not a fictitious unauthenticated account. [Nested observation](../evidence/phase2/doctor-nested.json) and [host observation](../evidence/phase2/doctor-host.json) show the distinction. Running an OS sandbox outside an enclosing sandbox required explicit tool approval; no adapter can escalate or retry itself unrestricted.

`python3 -m agentkit.sandbox_probe` runs offline disposable canaries on supported macOS contexts. [Complete measurements](../evidence/phase2/sandbox-canaries-complete.json) retain parent checks. Read the [effective matrix](sandbox-matrix.md) before interpreting passes. Network-denied fake-HOME Codex configuration validation is preserved in [offline-config evidence](../evidence/phase2/codex-offline-config.json); it used no real auth and exposed built-in reconnects. It is not live success evidence.

## Live smoke evidence and usage

The user initially held live inference while billing overflow was unknown, then explicitly authorized existing-subscription smoke tests without further billing investigation. That later instruction is the execution authority. No billing settings, credentials, authentication methods, API keys or global CLI settings were changed. Per-call flags/environment applied only to child processes. There was no account purchase or paid-mode fallback.

The fixed synthetic input was `[17, 25]`; controller code independently computed `{"sum": 42}` and required exactly that object with an integer value, plus an unchanged empty cwd. A provider claiming success with 43 fails the same oracle in fixtures. Live bounds: 45 seconds, combined 1 MiB capture, one task, no tools, no session persistence; cleanup allowance follows the wall deadline. Claude requested one turn/512 output tokens/zero retries. Codex cannot set zero native retries for its built-in provider; reported reconnects terminate the process and hidden attempts remain unknown. No provider/auth switch was used to evade that limitation.

| Engine / evidence | Outcome | Provider-reported usage | Billing interpretation |
|---|---|---|---|
| [Claude original run](../evidence/phase2/live-claude/result.json), [redacted events](../evidence/phase2/live-claude/stdout.redacted.jsonl), [offline correction](../evidence/phase2/live-claude-replay.json) | Correct JSON; one turn; exit 0; 2.024 s supervised duration. Tools and MCP empty. Fixture passes on replay. | Input 2; cache creation 2,506; cached read 0; output 10; CLI cost estimate USD 0.02532. Reasoning tokens unknown. | Estimate is **not a charge**. Billed USD unknown. Stream reported current usage allowed and `isUsingOverage=false`; this is a run observation, not a billing audit or guarantee. |
| [Codex initial config failure](../evidence/phase2/live-codex/result.json) | Reserved provider override rejected; 0.140 s | Unknown | No inference evidence; do not infer zero billed usage from absent data. |
| [Codex guarded attempt](../evidence/phase2/live-codex-final/result.json), [startup error](../evidence/phase2/live-codex-final/stderr.redacted.txt) | Startup failed under guard; 3.288 s; cwd empty; group gone | All token/cost fields unknown | No usage/billing evidence. No permission relaxation or further live retry. |

Claude's `rate_limit_event` was an **allowed** status notification with metadata about unavailable overage. The initial generic string classifier mistook the event type for an active rate limit and sent TERM after the completed result was already captured; the process exited 0. The original failed controller record and cancellation signals remain intact. The fix distinguishes structured allowed/rejected status, and regression tests replay the archived stream and test actual rejected fixtures. The final corrected adapter has **not** been rerun live; its successful normalization is tested offline. This avoids another quota-consuming call merely to replace an inconvenient record.

Codex's final historical record uses generic `provider_error`; current offline replay classifies its exact startup error as `guard_denied`. It does not promote the failure to success. Runtime write denial is supported by canaries; the exact internal Codex operation denied is not diagnosed by reading user state or loosening the guard.

## Phase 3 recommendation

**Do not declare the full Phase 2 exit criterion passed or begin production delivery orchestration.** The specification requires both engines to complete a disposable task, and Codex did not. General credential/tool isolation is also unsupported. Both findings remain explicit gates.

Phase 3 design and offline controller fixtures can safely begin with execution disabled: versioned state, reconciliation, budget reservations, stale-approval rejection and a local disposable worktree broker. Enabling delivery runs must first resolve Codex's guarded startup without exposing or relocating real credentials or permitting global writes, then validate every advertised tool/credential/network boundary on each supported platform. Durable cancellation, detached processes and controller crash recovery also need their own gate. There is no approval to implement those later phases in this change.
