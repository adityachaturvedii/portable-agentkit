# Phase 4 graph, routing and resource semantics

## Intake and graph

`task submit` requires a fresh workflow root, task ID, natural-language request and one fixture from `task fixtures`. The persisted contract records objective, scope, observable acceptance criteria, non-goals, dependencies, risk, difficulty, the `trusted-disposable-macos` profile and resource bounds. The original request is a user requirement; the listed controller interpretations are assumptions. The request cannot grant new authority.

Single mode uses implementation → verification → review → package. Decomposed mode schedules two independent implementation nodes, integrates their disjoint broker-validated commits into the controller-owned candidate, then verifies and reviews the integrated revision. Intake/planning/scheduling/integration/package nodes are deterministic. A normal dependency edge must form a DAG and exactly match the node's dependency list. Repair is an explicit bounded edge back through verification and review; two cycles are the maximum.

The limits are twelve nodes, two implementation subtasks, two concurrent executions and two repairs. A node cannot start until all persisted dependencies have succeeded. Cancellation prevents subsequent launches; during a supervised live call, the process transport polls the durable flag and terminates its process group. Reserved/running executions found after restart become uncertain and block replacement until explicitly reconciled. Detached children, a crashed controller and remote cancellation remain unsupported.

## Routing

The registry contains Codex and Claude Code account-default profiles. Submission may select the implementation and review provider:

```sh
python3 -m agentkit task submit --root /tmp/agentkit-task --task-id demo \
  --fixture inventory --request "Repair the inventory fixture" \
  --implementer-provider codex --reviewer-provider claude
```

Each route records provider, nullable model, nullable effort, role, required capability, relative-cost evidence and reason. No exact model identifier is configured because the tested CLI/account combination does not expose a trustworthy complete inventory without making unsupported assumptions. Availability is established by the adapter's read-only preflight when execution starts. Relative cost and quality remain unknown, so the explicit account-default route is the least-expensive adequate choice only according to the available evidence: it makes one implementation call per needed subtask and adds no larger model or second implementer.

Routine tasks select the single workflow. Substantial tasks decompose only where fixture interfaces are independent. Material/substantial tasks require the reviewer to differ from the implementation provider. If no enabled profile provides the required owned-code or model-only capability, routing fails before execution. A failed acceptance check or concrete review finding can invoke the configured repair route; escalation is bounded by the node and task repair limits.

## Budgets and usage

The controller atomically reserves every execution. It enforces maximum calls, local concurrency, elapsed allocations, per-call timeout and graph/repair bounds. Implementation/repair must preserve one verification and one review call; verification must preserve the review call. Failed and authentication-failed calls remain accounted. Authentication waiting consumes no active execution capacity or repair count.

Each provider request is limited to 1 MiB captured output. The tested CLIs manage their context windows, so context allocation is recorded as `provider-managed-unknown`. Provider token categories are reported separately as input, output, cached input, cache creation and reasoning where available. Missing telemetry remains `null`. Estimated cost and billed cost are separate and remain `null` here; a post-call estimate would not be a hard dollar cap or billing statement.

## Context and approval

The planner selects only relevant audited skill/domain files and persists each relative path, reason and SHA-256. Workers receive structured handoffs, not complete transcripts. Controller state and evidence remain authoritative; summaries and model recommendations are untrusted until independently checked.

The final package includes base/head, branch, diff, verification, active and resolved findings, routing, skill hashes, resource observations, limitations and proposed PR text. It stops at `awaiting_pr_approval`, records no approval and performs no push, PR, merge or deployment.
