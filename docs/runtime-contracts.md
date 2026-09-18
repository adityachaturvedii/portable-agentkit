# Phase 2 adapter contracts (version 1)

The canonical typed contracts are [runtime_contracts.py](../agentkit/runtime_contracts.py). They use Python 3.9+ dataclasses and JSON-compatible values, with no SDK dependency. The provider wire translators are separate `CodexAdapter` and `ClaudeAdapter` classes in [adapters.py](../agentkit/adapters.py); process supervision is shared. These are trusted-controller interfaces, not worker-granted authority.

## Records and semantics

| Record | Stable fields and rules |
|---|---|
| `Capability` | `state`: `verified`, `unavailable`, or `unknown`; `evidence` describes exactly what was observed. Help advertising a flag does not verify its enforcement. |
| `EngineCapabilities` | Version 1; `engine`, nullable `executable`, `version`, `executable_sha256`; capability map `features`; `authentication` and `authentication_mode`; `billing_mode`, `paid_overflow`, `provider_details`. A launcher hash does not attest all code it loads. |
| `ExecutionRequest` | Version 1; engine (`codex`/`claude`), nonempty `task_id` ≤128 characters, prompt ≤32 KiB UTF-8, absolute `cwd`; finite timeout 0.05–300 seconds, combined output limit 1 KiB–4 MiB, optional model, mode. Unknown JSON fields and schema versions are rejected. Defaults: 30 seconds, 1 MiB, `model-only`. |
| `LivePolicy` | Separate trusted caller input. Default deny; explicit subscription-smoke authorization and evidence required. It cannot be supplied in request JSON. This object/CLI flag is not an authenticated approval ledger. |
| `ExecutionBoundary` | Separate trusted caller input for `owned-code`: absolute disposable workspace plus at least one absolute denied-read path. It cannot be supplied by a worker result and does not enumerate every host secret. |
| `ExecutionResult` | Version 1; engine/task, status (`succeeded`, `failed`, `cancelled`, `blocked`), nullable error class and exit code, measured elapsed seconds, nullable session/model/final text/object output; usage, cancellation, artifact hashes, provider details and limitations. Provider success is not fixture acceptance. |
| `UsageObservation` | Nullable nonnegative token counts: input, output, cached input, cache creation, reasoning; nullable estimated and billed USD, source, final flag, provider details. Missing or invalid quantities remain `null`. `billed_cost_usd` is always unknown here. No currency conversion, guessed token accounting, or summing overlapping provider counters. |
| `CancellationStatus` | Requested/reason, TERM/KILL sent, leader reaped, nullable process-group-gone, explicit scope. Neither group disappearance nor a zero exit establishes remote cancellation. |

Adding a provider requires an explicit compatibility review and adapter. Provider-specific fields remain in `provider_details`; they confer no authority. A breaking field/meaning change requires a new schema version. `ExecutionRequest.from_dict` is the validating request boundary. Results are emitted by the controller; Phase 2 does not deserialize result JSON into executable instructions or approvals.

## Transport and outcomes

Commands are argument arrays with stdin, never shell command strings. Capture is byte-bounded in memory, with UTF-8/duplicate-key/nonfinite/depth checks before JSONL normalization. One terminal provider event is required. Unterminated records or missing terminals produce `truncated_output`; invalid encoding/JSON, duplicate terminals or invalid shapes produce `malformed_output`. Unknown event types are retained as redacted raw events and grant no success or capabilities. Normalized `structured_output` comes from a provider structured object or strict JSON final text; it is not a full JSON Schema validator.

Other error classes include `authentication`, `rate_limit`, `usage_limit`, `network`, `provider_error`, `guard_denied`, `sandbox_unavailable`, `timeout`, `cancelled`, `interrupted`, `output_limit`, `missing_executable`, `launch_error`, `retry_requested`, and `unexpected_tools`. Preflight can block with `billing_policy`, `unsupported_isolation`, `incompatible_cli`, `authentication`, or `fixture_not_empty`. Errors remain visible; there is no retry loop or unrestricted fallback.

Timeout/cancellation sends TERM to a new POSIX process group, then KILL after a short grace. The leader is reaped; remaining same-group children are cleaned even after a successful leader exit. Stream collection and cleanup are bounded, including lingering inherited pipes. Timeout measures the execution subprocess, with up to roughly two seconds additional cleanup; diagnostic preflight is separately bounded. Windows process supervision is unsupported. Detached descendants, remote actions, controller SIGKILL/crash recovery and process-count/resource isolation remain outside this contract.

The stream monitor stops on explicit usage/auth/rate failures, reported retries and unexpected tool surfaces. Claude `rate_limit_event` with `status=allowed` is metadata, not a failure; `status=rejected` stops execution. UUID digits and benign metadata must not trigger error classification. Unit fixtures and the archived live stream cover this distinction.

## Managed scope and evidence

`execute` accepts only `model-only`, an empty disposable directory, a reviewed CLI version, verified subscription status and an effective whole-process macOS write guard. `execute_owned_code` additionally requires a trusted `ExecutionBoundary` and `owned-code` mode. `untrusted` remains blocked. Auth status is queried through official commands under a no-network/no-global-write guard; the toolkit never reads credential contents itself. Child environments use an allowlist, stripping API keys, auth overrides, proxy/provider overrides, loader variables and retry-watchdog settings. A trusted installed CLI and trusted local policy remain prerequisites.

The model-only guard allows runtime writes plus Codex's literal installation-identifier lock file. Owned-code allows a disposable workspace/runtime plus one provider startup path, and denies controller-selected protected reads. Codex identifier integrity is compared before/after; Claude receives a preselected fresh session path that is removed after execution. The parent retains provider network and required auth access. No supported mode promises comprehensive OS credential or tool-network isolation.

Nested native macOS command sandboxes fail inside the whole-process Seatbelt profile. Owned-code therefore uses the external profile as its sole OS boundary and records this as `external-seatbelt-owned-code`. Provider-native tool sandboxing is disabled only within that outer guard. This mode is for trusted synthetic fixtures; it is not an untrusted-repository boundary.

One controller launch per smoke; no provider switch. Claude requests zero native retries, one turn and 512 output tokens. Codex's built-in provider rejects retry overrides: managed wall time bounds it and reported reconnects stop it; hidden attempts remain unknown. A strict zero-provider-attempt-retry requirement is unsupported for this Codex version. No monetary ceiling or account billing assertion is inferred from these controls.

Each fresh output directory contains a prompt-hash request summary, `stdout.redacted.jsonl`, `stderr.redacted.txt`, and `result.json` with artifact SHA-256s. `execution-check` adds `acceptance.json`, which requires an exact successful test-command event, immutable controller test, changed-file manifest and unchanged fake canaries. Original event order/fields remain except redactions and JSON serialization; these are not byte-identical original streams. Known credential fields/patterns and thinking/signature fields are removed before persistence. Output-limit fragments are withheld. This is not a universal secret detector: callers must use synthetic prompts. Directories/files are created 0700/0600; Git does not preserve these privacy modes on checkout. Never store real secrets as fixtures.

Existing output directories are refused before execution. Artifact persistence is a local completion record, not crash-safe transactional storage, an authenticated event journal, concurrent reservation, or a Phase 3 controller. Failure during persistence does not undo a remote request. Request prompt hashes omit the prompt; [smoke.py](../agentkit/smoke.py) contains the reproducible synthetic input and independent integer-sum oracle.
