# Phase 4 graph, routing and resource semantics

## Intake and graph

`task propose` and `task submit` require a natural-language request and one controller-created project from `task fixtures`. The planner receives only that request, a bounded path/size/hash/interface inventory, verified capabilities, selected skill provenance and declared resource limits. It produces objective, sourced requirements, assumptions, observable acceptance, assignments, writable paths, interfaces, dependencies, integration, verification/review requirements, roles, routing placeholders and allocations. Expected patches are controller fixture data and never enter the proposal or worker context.

Deterministic planning uses request terms, declared interfaces and project metadata. A request can select a bounded subset only when that subset has its own controller-owned acceptance test. Contradictory case requirements produce `ClarificationRequired`; routine authorized work needs no further permission. The validator rejects changed acceptance, inventory mismatch, unsafe or out-of-contract paths, unknown dependencies, cycles, excessive fan-out, concurrent path overlap and plans that cannot fit call/time/concurrency budgets. Model-produced proposal documents may be supplied only through a future explicitly configured planner transport; unaccounted model planning is rejected.

Single mode uses implementation → verification → review → package. Decomposed mode uses up to two assignments, each with a separate branch/worktree and plain worker copy. The scheduler atomically claims ready nodes and launches at most two provider executions through `ThreadPoolExecutor`; synchronized fixture tests prove actual overlap. Dependency nodes wait for predecessor success. Only the controller integrates clean broker-validated contributions. Overlap/conflict blocks without deleting either contribution.

Node claims persist controller owner/PID before provider execution. A second controller observing a confirmed-live owner reports current state and does not launch duplicates. A dead or unprovable owner blocks replacement and requires reconciliation; no timer expires ownership. Cancellation marks every active execution and each supervised transport observes the durable flag. Authentication failure finalizes only that call, lets independent siblings finish, then creates one stage checkpoint. Detached children, process survival after controller crash and remote cancellation remain unsupported.

The first bounded live concurrency attempt launched two Codex workers concurrently and retained one valid contribution. It blocked before integration when the other worker could not create a zsh heredoc temporary file or use Git's `/dev/null` config sink under the owned-code profile. Revision `b9df1ad` makes only those two runtime accommodations and passes offline and host boundary checks. Since no provider call was repeated, complete live integration, verification and cross-provider review remain unverified for the corrected revision.

## Routing

The registry contains Codex and Claude Code account-default profiles. Submission may select the implementation and review provider:

```sh
python3 -m agentkit task submit --root /tmp/agentkit-task --task-id demo \
  --project inventory --request "Repair pricing and stock calculations" \
  --implementer-provider codex --reviewer-provider claude
```

Each route records provider, nullable requested model, nullable requested effort, role, capability, evidence and reason. `--routing-config FILE` loads a portable registry. Profiles declare eligible roles/capabilities, exact model or account default, supported effort, availability state, evidence source/date and optional relative cost/quality evidence. Policies match role, capability, difficulty, risk and optional node. Exact models loaded from JSON need dated availability evidence; `unverified` and `unavailable` profiles are ineligible. Account defaults remain explicit because the CLIs do not expose a complete trustworthy model inventory.

Availability is established by the adapter's read-only preflight when execution starts. Relative cost and quality remain unknown unless the registry has concrete evidence. The policy chooses an explicit default or a profile marked lower cost; this is a deterministic rule, not calibrated model optimization. It makes one implementation call per needed subtask and adds no larger model or second implementer.

Requested configuration reaches the actual CLI request. Provider-reported model/effort stays separate and unknown when absent. The installed Claude CLI contract permits `low`, `medium`, `high`, `xhigh` and `max`; Codex effort is rejected. Evidence marked `lower` may guide routing; absent comparative evidence uses the configured default and is never described as cost-optimal. Material/substantial plans exclude every implementation provider and any configured repair provider from review. If independence cannot be satisfied, planning fails rather than substituting or weakening review. Repair/model escalation occurs only after a concrete failed check or validated finding and is bounded by both repairs and escalations.

## Budgets and usage

The controller atomically reserves every execution. It separately enforces total calls, provider calls, planning calls, local concurrency, elapsed allocations, per-stage/per-call timeout, graph/subtask, repair, retry and escalation bounds. Implementation/repair preserves total verification and review calls and also preserves the provider review slot. Planning validates the sum of mandatory time allocations before execution. Failed and authentication-failed calls remain accounted. Authentication waiting consumes no active execution capacity or repair count.

Each provider request is limited to 1 MiB captured output. The tested CLIs manage their context windows, so context allocation is recorded as `provider-managed-unknown`. Provider token categories are reported separately as input, output, cached input, cache creation and reasoning where available. Missing telemetry remains `null`. Estimated cost and billed cost are separate and remain `null` here; a post-call estimate would not be a hard dollar cap or billing statement.

## Context and approval

The planner selects audited skill/domain files and persists each relative path, applicable roles, reason and SHA-256. Immediately before a provider call, the controller resolves the path under the toolkit root, requires a regular UTF-8 file, rechecks its hash and applies per-file and per-role byte limits. The implementer/repair context includes behavioral-testing and the fixture domain; the reviewer context includes independent-review and the fixture domain. Other selected planning/delivery skills are not dumped into those prompts. Workers receive this structured handoff rather than complete transcripts. Controller state and evidence remain authoritative; summaries and model recommendations are untrusted until independently checked.

The final package includes base/head, branch, diff, verification, active and resolved findings, routing, skill hashes, resource observations, limitations and proposed PR text. It stops at `awaiting_pr_approval`, records no approval and performs no push, PR, merge or deployment.
