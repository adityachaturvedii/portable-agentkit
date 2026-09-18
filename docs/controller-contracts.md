# Phase 3 controller contracts

The canonical implementation is [controller.py](../agentkit/controller.py). These are local trusted-controller records. Worker and model output is untrusted data and has no authority to invoke state, budget or approval mutations.

## Task states

The normal path is:

`received -> contracted -> workspace_ready -> implementing -> implemented -> verifying -> verified -> reviewing -> review_complete -> packaging -> awaiting_pr_approval`

Verification or concrete review findings can enter `repairing`, which returns only to `implemented`. A classified provider authentication failure from `implementing`, `repairing`, or `reviewing` enters `authentication_required` through the dedicated recovery method. Only a verified first-party subscription login can restore the exact interrupted state. `blocked` and `cancelled` remain terminal. Every transition validates its expected source state inside the same transaction that appends its event. Dependency tasks must be at `awaiting_pr_approval` before a dependent task can enter `workspace_ready`.

Execution roles are state-bound: `implementer` to `implementing`, `repair` to `repairing`, `verification` to `verifying`, and `reviewer` to `reviewing`. Reservation and start both check this mapping. Any `reconciliation_required` execution blocks new reservations until the controller records an explicit `not_started` or `terminated` resolution. Resolution releases held capacity but deliberately leaves the task blocked for a new trusted recovery decision.

## Durable records

| Record | Required semantics |
|---|---|
| Task | ID, objective, validated contract, dependencies, implementer/reviewer engine and model, base/head revisions, branch/worktree, repair count, state, version and next action. |
| Event | Unique event ID, task, type, JSON payload, timestamp and monotonic database sequence. Rows cannot be updated or deleted. |
| Budget | Maximum and current calls, elapsed allocation, concurrency, timeout and verification reserve. Reservations use one immediate transaction before launch. |
| Execution | Role, engine/model, allocation, lifecycle status, optional process identity, measured elapsed time, usage observation, result details and reconciliation note. |
| Evidence | ID, task, exact revision, kind, status, content hash, details, stale flag and timestamp. Evidence for a noncurrent revision is rejected. |
| Approval | ID, task, repository, branch, exact head, action, expiry, source and stale flag. It can be written only through controller authority after `awaiting_pr_approval`. |
| Failure signature | Stable signature, count and concrete details. A repeated signature or exhausted repair count blocks the task. |
| Authentication checkpoint | Provider/account context, interrupted role/state, failed execution, exact candidate, evidence references, bounded attempt count and sanitized status. No secrets or transcripts. |
| Authentication session | One active interactive login per provider/account context, shared by waiting tasks and resolved only from an official sanitized status probe. |

## Usage and limits

`UsageRecord` preserves nullable input, output, cached-input, cache-creation and reasoning token counters plus nullable estimated and billed cost. Missing values remain unknown. Provider-reported categories are not converted into exact limits or billing claims.

All call/concurrency/repair/reserve counts require real integers and reject Boolean values. Elapsed limits and timeouts require finite positive integers or floats; completed elapsed time and observed costs require finite nonnegative values. NaN and either infinity are invalid.

The controller can enforce reservation count, local concurrency, wall-time allocation and request timeout. It cannot enforce an exact provider token ceiling or monetary cap through the current CLI adapters. Capacity reserved for verification cannot be consumed by implementer or reviewer calls.

## Revision and approval binding

The Git broker creates the base and candidate revisions. `set_head` invalidates evidence and approvals for older heads. Independent verification and review name the candidate revision, and packaging checks current passing evidence before producing a local package. The package itself is evidence, not approval. Worker text, provider terminal status or a package field cannot create a user approval.

Independent verification reads the committed source into a fresh `/private/tmp` copy and writes the controller-owned acceptance test there. A macOS Seatbelt profile denies network, Mach service lookup and all writes except disposable runtime state; it denies reads of controller state, approvals, evidence, the managed repository/worktree and the invoking home. The child receives an allowlisted environment with an empty disposable `HOME`. Source/test manifests and the original worktree revision, cleanliness and manifest must remain unchanged. Absence of this verified profile blocks verification rather than falling back.

When a check fails, the next repair prompt includes controller-generated JSON. Verification feedback contains the exact candidate revision, acceptance criteria, exit/stop status and at most the final 8 KiB of redacted test output. Review feedback contains the exact revision and already validated concrete findings. This data remains advice to the worker; it grants no authority.

## Restart semantics

On restart, the controller inspects reserved, running and cancellation-requested rows before any replacement launch. Without independently established process ownership, it marks them `reconciliation_required`, records a reconciliation event and blocks the task. SQLite durability alone is not process containment. Detached descendants and remote cancellation remain unsupported.

An `authentication_required` task is already free of active execution reservations and survives restart as a recoverable checkpoint. Login waiting does not consume calls, elapsed allocation, concurrency or repair count. Resume rejects any subsequently discovered `reconciliation_required` execution, changed candidate, stale referenced evidence, non-subscription login or arbitrary blocked state. See [guided authentication recovery](authentication-recovery.md).
