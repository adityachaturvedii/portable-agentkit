# Phase 2 execution follow-up

Observed on macOS Darwin 25.6.0 arm64 with Codex 0.154.0, Claude Code 2.1.220 and Python 3.9.6 on 2026-09-19.

## Provenance and scope

The expected Phase 2 revision `6bfb981670a1f4e553c870995414452f2ce06b21` existed and its worktree was clean. The reported suite reproduced at 60/60 tests. Follow-up work was created from that exact commit in the dedicated `implementation/phase-2-execution` branch and `portable-agentkit-phase02-execution` worktree. No merge, push or PR was performed.

The [follow-up manifest](../evidence/phase2-followup/manifest.json) binds 35 evidence files by SHA-256 and is replayed by the offline test suite.

## Startup diagnosis and corrections

Codex `exec` starts an in-process app server before a turn. Version 0.154.0 resolves its installation identifier during that startup. The implementation opens `$CODEX_HOME/installation_id` read/write and locks it even when the existing 36-byte identifier is valid. This explains the retained `failed to initialize in-process app-server client: Operation not permitted` record under the original blanket write guard. The relevant upstream implementation is [`in_process.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/app-server/src/in_process.rs), and the behavior is also tracked in [openai/codex#42398](https://github.com/openai/codex/issues/42398). OpenAI documents `CODEX_HOME` as the location for Codex auth/config/state and `CODEX_SQLITE_HOME` separately for SQLite state in the [environment-variable reference](https://developers.openai.com/codex/config-file/environment-variables).

The correction permits writes to the literal existing `~/.codex/installation_id` file, not its directory. The adapter verifies that it is a regular non-symlink and compares its SHA-256, size and mode before and after execution. Both live Codex attempts observed the same hash, size and mode. An offline startup probe and the final coding run passed this point.

Claude's built-in Bash tool requires two transient locations before executing a command: `~/.claude/session-env/<session-id>` and a per-user temporary tree. The adapter now preselects the session UUID, permits only that fresh session path, sets `CLAUDE_CODE_TMPDIR`/`CLAUDE_TMPDIR` to the disposable runtime, and removes the created session path after the run. Redirecting the entire Claude config directory was rejected because it hid the existing subscription login. Earlier failed attempts are retained as evidence rather than overwritten.

Native macOS tool sandboxes cannot initialize from inside the whole-process Seatbelt profile: Codex returned `sandbox_apply: Operation not permitted`. The supported owned-code mode therefore uses the explicit whole-process Seatbelt profile as its sole OS filesystem boundary. Codex's inner tool sandbox is set to `danger-full-access` only inside that outer boundary; Claude's inner Bash sandbox is disabled there. The outer profile still denies all writes except the disposable workspace/runtime and the one preselected CLI state path, and explicitly denies reads of controller-selected protected paths. Provider and tool traffic share one network boundary, so tool egress isolation is unsupported in this mode.

## Live coding acceptance

Each final run received a fresh fixture containing a broken `add` function and immutable unit test. The CLI had to read both files, edit only `arithmetic.py`, and run exactly `python3 -B -m unittest -v`. Acceptance required a successful provider command record, one changed file, an unchanged test, unchanged canaries, and a separate controller rerun of the immutable test.

| Engine | Result | Provider command | Independent acceptance | Evidence |
|---|---|---|---|---|
| Codex 0.154.0 | Passed in 22.221 s | Exact unittest command exited 0 and reported one passing test | Controller rerun passed; only `arithmetic.py` changed | [`result`](../evidence/phase2-followup/live-codex/result.json), [`acceptance`](../evidence/phase2-followup/live-codex/acceptance.json), [`events`](../evidence/phase2-followup/live-codex/stdout.redacted.jsonl) |
| Claude Code 2.1.220 | Passed in 13.473 s | Exact Bash tool command produced a successful terminal record with `OK` | Controller rerun passed; only `arithmetic.py` changed | [`result`](../evidence/phase2-followup/live-claude/result.json), [`acceptance`](../evidence/phase2-followup/live-claude/acceptance.json), [`events`](../evidence/phase2-followup/live-claude/stdout.redacted.jsonl) |

Retained negative records cover the Codex nested-sandbox failure and Claude's session-state, config-redirection-auth and temporary-state failures. They establish why each narrow exception or redirect exists.

## Boundaries and lifecycle

The exact external filesystem profile independently denied read and write attempts against a sibling workspace file, fake-credential canary and controller-state file, while allowing a workspace write. Parent verification found every canary unchanged. See the [boundary record](../evidence/phase2-followup/boundary/boundary.json).

Offline timeout and cancellation cases ran a TERM-resistant leader and child under the same profile. Both sent TERM then KILL, reaped the leader, removed the same process group and independently confirmed the child PID was gone. See the [lifecycle record](../evidence/phase2-followup/lifecycle/lifecycle.json). Detached descendants, pre-existing services, controller crash recovery and remote provider cancellation remain unsupported.

## Usage observations

No CLI reported a usage limit or payment requirement. No API key, billing setting, credit purchase or authentication method changed.

| Engine / attempts | Provider-reported tokens | Cost observation |
|---|---|---|
| Codex: nested-sandbox failure plus accepted run | input 65,960; cached input 53,504; output 358; reasoning 33 | Estimated cost unknown; billed cost unknown |
| Claude: session-state failure, temp-state failure and accepted run | input 34; cache creation 14,123; cached read 83,604; output 4,408 | CLI estimates total USD 0.293402; this is not a bill or proof of a charge. Billed cost unknown |
| Claude config-redirection auth failure | All usage fields unknown | Estimate and billing unknown |

Provider token fields may overlap and are not converted into a new cost estimate. Purchased-credit or overflow use remains unknown and was not reinvestigated.

## Capability classification and recommendation

**Implemented and tested:** provider-neutral owned-code boundary contract; separate tool-aware event normalization; exact-path startup allowances; disposable coding fixture; independent command/file/test oracle; fake-canary read/write probe; local timeout/cancellation and same-group cleanup; both bounded subscription CLI coding runs on this host.

**Simulated/offline:** malformed/truncated/auth/rate/usage/missing-executable fixtures from the original Phase 2 suite; TERM-resistant timeout and cancellation; provider-limit stopping without deliberately consuming quota.

**Unverified or unsupported:** general real-credential isolation, tool-specific network egress, hostile repositories/prompts, unrestricted local projects, native-sandbox nesting, detached-process containment, remote cancellation, Linux/WSL2/Windows, controller crash recovery, Codex hidden native retry count and billing attribution. Reported reconnects stop a run, and wall time remains the outer bound.

Phase 3 may begin for **trusted, controller-created disposable workspaces on this tested macOS host**, using the external Seatbelt owned-code mode with explicit protected paths. Model-only Claude remains supported from Phase 2; the Codex startup correction is implemented for model-only mode but was validated here through startup and the owned-code path rather than another quota-consuming model-only call.

Do not enable Phase 3 for untrusted repositories, arbitrary user prompts, broad local-project execution, or jobs requiring tool-network/complete credential isolation. Those modes are blocked by the inability to separate provider network/auth access from tool access inside one CLI process and by unsupported nested native sandboxes.
