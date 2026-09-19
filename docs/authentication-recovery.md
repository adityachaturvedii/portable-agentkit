# Guided authentication recovery

This implementation supports only first-party subscription authentication for the installed Codex CLI and Claude Code. It does not accept API keys, create OAuth clients, move credential files, select Console billing, or change global CLI settings.

## Supported commands

The commands were selected from the installed CLI help and the providers' official documentation:

| Provider | Status | Browser login | Callback fallback |
|---|---|---|---|
| Codex CLI | `codex login status` | `codex login` | `codex login --device-auth` shows an official URL and one-time device code. |
| Claude Code | `claude auth status --json` | `claude auth login --claudeai` | The same command prompts for the code shown by the official browser page when its localhost callback cannot reach the CLI. |

References: [OpenAI Codex authentication](https://developers.openai.com/codex/auth) and [Claude Code authentication](https://code.claude.com/docs/en/authentication).

Use the toolkit's sanitized status command without starting inference:

```sh
python3 -m agentkit auth-status codex
python3 -m agentkit auth-status claude
```

For a workflow stopped at `authentication_required`, run login in your own terminal from this checkout:

```sh
python3 -m agentkit auth-login claude \
  --workflow /absolute/path/to/workflow \
  --task-id phase3-demo
```

For Codex, browser login is the default. Add `--method device` when the browser callback cannot reach the CLI. Claude's browser flow already provides its supported manual code prompt fallback.

The command first reuses a working subscription login. Otherwise, it identifies the provider and local machine, then attaches the official CLI directly to the terminal. Standard input, output and error are inherited rather than piped. Passwords and MFA remain on the official page, and any authorization code is entered only into the official CLI prompt. The controller receives only a bounded result category and sanitized subscription status. If no safe TTY is available, the command prints the exact official CLI command and leaves the checkpoint unclaimed.

After successful login, resume only the interrupted stage:

```sh
python3 -m agentkit controller-demo \
  --output /absolute/path/to/workflow \
  --live --implementer codex \
  --authorize-subscription-smoke --resume
```

If a controller or terminal ended while a login was marked in progress, a second login is not started. First establish process state. A confirmed-ended process can be released with a sanitized, categorical record:

```sh
python3 -m agentkit auth-reconcile \
  --workflow /absolute/path/to/workflow \
  --task-id phase3-demo \
  --resolution confirmed_ended \
  --basis process_exit_confirmed
```

Use `--resolution uncertain --basis process_termination_unconfirmed` when termination cannot be established. That keeps the checkpoint blocked until process evidence is available. A timeout by itself never releases login ownership, and free-form terminal output is not accepted into the reconciliation record.

## Recovery contract

An authentication checkpoint contains the task, provider, subscription account context, interrupted role/state, failed execution ID, candidate revision, controller-owned repository/worktree identity, clean manifest digest and relevant evidence IDs. It contains no account identifier, URL, authorization code, token, raw login output or credential path. Checkpoints are historical records: one task can encounter sequential Codex and Claude failures or repeat expiry, while a partial unique constraint permits only one active checkpoint for that task.

Schema v2 stores migrate transactionally and retain their checkpoint history, but an active v2 checkpoint has no checkpoint-time worktree manifest. It therefore cannot satisfy the new resume proof and fails closed; completed task state and evidence remain intact. A replacement run must establish a new fully bound checkpoint rather than retroactively inventing identity evidence.

The failed inference is finalized before the checkpoint is created. Its observed elapsed time and provider-reported usage remain recorded; missing usage remains unknown. Waiting for login consumes no execution reservation or repair attempt. One active login session is allowed per provider/account context, and each checkpoint permits at most two interactive attempts. The login owner has a process identity and controller-only ownership nonce that is excluded from events, evidence, snapshots and model input. `in_progress`, `reconciliation_required`, confirmed-ended and terminal outcomes are distinct durable states.

Resume requires all of the following:

- the official status command reports first-party subscription authentication;
- the failed execution is durably finished;
- no execution is active or awaiting reconciliation;
- task state is exactly `authentication_required`;
- the actual controller-owned repository path, worktree path, branch, Git HEAD, clean status and complete file-manifest digest still match the checkpoint;
- candidate revision and referenced evidence are unchanged and current, and each referenced artifact still matches its content hash; and
- the checkpoint names an implementer, repair, or reviewer stage.

Cancelled, failed, or timed-out login leaves a recoverable checkpoint. Ctrl+C terminates and reaps the official login process group where this can be established; launcher failures with uncertain termination enter explicit reconciliation instead of reopening login. Network, quota, rate-limit, permission, sandbox and ordinary execution failures do not create authentication checkpoints. A changed candidate, dirty worktree, wrong branch or repository, stale evidence, non-subscription login or unresolved execution blocks resume before task state changes or approval packaging. PR approval remains separate and revision-bound.

Phase 4 task workflows use these same checkpoint and login-session records. The checkpoint execution must identify exactly one persisted graph node in `authentication_required`. `python3 -m agentkit task resume --root ROOT --task-id ID --live --authorize-subscription-smoke` restores only that node and interrupted stage after the controller recomputes the actual candidate identity. Completed specialist branches, integration work, valid verification evidence, usage and repair counts remain intact.

## Security boundary

Login is a trusted controller-side operation outside the worker sandbox. The subprocess gets the normal user home required by the official CLI, a credential-scrubbed environment, a neutral `/private/tmp` working directory, and direct terminal streams. The CLI manages its own credential storage. This mode does not claim that the provider CLI cannot read other user files or that browser/Keychain access is fully isolated.

Interactive login transcripts are deliberately not captured, redacted, hashed, persisted or sent to a model. This is stronger than recording first and redacting later. Fixture tests use synthetic secrets and confirm that durable events, evidence, controller snapshots, result objects and resumed prompts exclude them.

The completed live delivery used existing working subscription authentication on the tested macOS host; no interactive login was needed. The browser/device login flow, manual browser-code handoff, sequential checkpoints, interruption handling and stage-specific resume are fixture-tested only. This corrective pass spent no live inference quota. Other platforms, remote login terminals, custom credential stores, enterprise policies and non-subscription authentication remain unverified.
