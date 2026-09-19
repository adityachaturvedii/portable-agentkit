# Phase 3 corrective review

Date: 2026-09-19 (Australia/Melbourne)

Starting revision: `17eba897c2cada2957642c36a4c5ddfb5d967a7b`

Branch/worktree: `implementation/phase-3-review-fixes` at `portable-agentkit-phase03-review`

## Finding verification and corrections

| Finding | Verification against starting code | Correction and behavioral evidence |
|---|---|---|
| Repair lacked failure context | Confirmed. Every implementation attempt received the same static prompt; failed test output and `review.findings` stayed only in controller records. | The next repair prompt now carries controller-generated JSON bound to the failed revision. Tests use implementers that repair only after receiving the expected failed unittest output or structured review criterion. |
| Verification was not independently constrained | Confirmed. `_verify` ran `python3 -m unittest` directly in the real Git worktree with inherited `PATH`, no OS read/network boundary and no post-test candidate manifest. | `ConstrainedVerifier` copies only committed `calculator.py` beside controller-owned `TEST_SOURCE`, replaces `HOME`, allowlists environment variables, denies network, Mach service lookup, writes and protected reads with Seatbelt, and compares the source/test copy plus original revision, cleanliness and manifest afterward. |
| Execution lifecycle ignored task state | Confirmed. `reserve_execution` checked only budget and `start_execution` checked only execution status. Terminal or reconciled-blocked tasks could retain launchable records. | Reservations and starts now enforce a four-role state map and reject every other state. Outstanding `reconciliation_required` rows block reservations. Explicit `not_started`/`terminated` resolution releases held capacity; the task remains blocked. |
| Budget/timeout validation accepted ambiguous numbers | Confirmed. Ordinary comparisons admitted Booleans in integer fields, and NaN could evade positive/range checks. `finish_execution` and cost observations also lacked finiteness checks. | Exact integer/numeric types plus `math.isfinite` now enforce positive counts/timeouts and nonnegative elapsed/cost values. Parameterized tests cover negative, zero, Boolean, fractional-count, NaN and positive/negative infinity inputs. |
| Failure event IDs could collide across tasks | Confirmed. Globally unique event IDs were `repair-allowed-<signature>`, `failure-repeat-<signature>` and `repair-exhausted-<signature>` without task identity. | Every failure/repair event ID now starts with the task ID. Two tasks recording the same signature succeed with disjoint event histories. |

## Verification boundary evidence

The boundary regression uses only disposable canaries. Synthetic candidate code attempts to read controller state, an approval package, repository Git configuration, the actual candidate source and a fake credential. It also checks for a synthetic `OPENAI_API_KEY` in its environment and attempts to overwrite its verification copy. The controlled unittest passes only when every read/write/environment attempt is denied. The parent then confirms all canaries and the candidate identity are unchanged.

The test reports unavailable inside an enclosing sandbox because nested `sandbox_apply` is prohibited. It passed on the same host execution context used for the Phase 2 external Seatbelt validation:

```text
test_candidate_cannot_read_protected_paths_credentials_or_mutate_inputs ... ok
Ran 1 test — OK
```

The corrected deterministic demonstration also completed at `awaiting_pr_approval`. Its independent verification used mode `read-only-seatbelt-no-network`, exited 0, reported `candidate_unchanged: true`, denied six protected roots, and recorded distinct hashes for the controller-owned test and committed source. No approval was recorded.

This proves the enumerated filesystem/environment canaries on the tested macOS host. The profile also denies Mach service lookup rather than permitting candidate access to Keychain/XPC services. Real secrets and services were not probed, so universal credential isolation, hostile-code containment, detached-process containment, remote cancellation and other platforms remain outside the claim.

## Test coverage

The full suite contains 91 tests after this pass. New behavioral cases cover:

- failed-test feedback required for a successful repair;
- structured review findings required for a successful repair;
- terminal, wrong-role, stale-start and unresolved execution rejection;
- explicit reconciliation resolution;
- invalid numeric types, signs and nonfinite values;
- same-signature events across two tasks;
- a real host Seatbelt verifier run with protected canaries and immutable candidate/test assertions.

Ordinary nested execution may report the host-only verifier case as one skip. The final host run executes all 91 tests without a skip. Package checking, bytecode compilation and `git diff --check` are also required before commit.

## Live cross-provider status

Live cross-provider completion remains blocked and unverified. The retained Phase 3 attempt still ends at Claude review with `authentication` because its existing OAuth token had expired. This corrective pass did not change authentication, switch methods, add a key, investigate billing or spend quota on another inference run. Codex's prior live implementation and independent test remain partial evidence; they do not make the end-to-end live path pass.
