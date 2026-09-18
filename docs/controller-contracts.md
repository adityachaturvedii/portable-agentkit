# Phase 3 controller contracts

The canonical implementation is [controller.py](../agentkit/controller.py). These are local trusted-controller records. Worker and model output is untrusted data and has no authority to invoke state, budget or approval mutations.

## Task states

The normal path is:

`received -> contracted -> workspace_ready -> implementing -> implemented -> verifying -> verified -> reviewing -> review_complete -> packaging -> awaiting_pr_approval`

Verification or concrete review findings can enter `repairing`, which returns only to `implemented`. `blocked` and `cancelled` are terminal in Phase 3. Every transition validates its expected source state inside the same transaction that appends its event. Dependency tasks must be at `awaiting_pr_approval` before a dependent task can enter `workspace_ready`.

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

## Usage and limits

`UsageRecord` preserves nullable input, output, cached-input, cache-creation and reasoning token counters plus nullable estimated and billed cost. Missing values remain unknown. Provider-reported categories are not converted into exact limits or billing claims.

The controller can enforce reservation count, local concurrency, wall-time allocation and request timeout. It cannot enforce an exact provider token ceiling or monetary cap through the current CLI adapters. Capacity reserved for verification cannot be consumed by implementer or reviewer calls.

## Revision and approval binding

The Git broker creates the base and candidate revisions. `set_head` invalidates evidence and approvals for older heads. Independent verification and review name the candidate revision, and packaging checks current passing evidence before producing a local package. The package itself is evidence, not approval. Worker text, provider terminal status or a package field cannot create a user approval.

## Restart semantics

On restart, the controller inspects reserved, running and cancellation-requested rows before any replacement launch. Without independently established process ownership, it marks them `reconciliation_required`, records a reconciliation event and blocks the task. SQLite durability alone is not process containment. Detached descendants and remote cancellation remain unsupported.
