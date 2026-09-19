# Phase 4 terminal guide

Run commands from the toolkit checkout. Targets are controller-created disposable projects; paths to existing repositories are rejected because general repository onboarding is unsupported.

List scenarios and inspect a request-derived proposal without creating a workflow:

```sh
python3 -m agentkit task fixtures
python3 -m agentkit task propose \
  --project text-metrics \
  --request "Repair word and line metrics"
```

Create an offline workflow with a two-worker ceiling and no repair/escalation:

```sh
python3 -m agentkit task submit \
  --root /tmp/agentkit-text-metrics \
  --task-id text-metrics-demo \
  --project text-metrics \
  --request "Repair word and line metrics" \
  --max-calls 4 \
  --max-provider-calls 3 \
  --max-planning-calls 0 \
  --max-concurrency 2 \
  --max-elapsed-seconds 190 \
  --implementation-timeout 60 \
  --verification-timeout 10 \
  --review-timeout 60 \
  --max-repairs 0 \
  --max-escalations 0 \
  --routing-config docs/examples/phase4-routing.json
```

Inspect and execute it with deterministic fixture providers:

```sh
python3 -m agentkit task plan --root /tmp/agentkit-text-metrics --task-id text-metrics-demo
python3 -m agentkit task start --root /tmp/agentkit-text-metrics --task-id text-metrics-demo
python3 -m agentkit task status --root /tmp/agentkit-text-metrics --task-id text-metrics-demo
python3 -m agentkit task package --root /tmp/agentkit-text-metrics --task-id text-metrics-demo
```

The equivalent explicitly authorized live start is:

```sh
python3 -m agentkit task start \
  --root /tmp/agentkit-text-metrics \
  --task-id text-metrics-demo \
  --live \
  --authorize-subscription-smoke
```

Live mode uses existing subscription authentication only. It does not add API keys, billing fallback or provider substitution. Stop a task with `task cancel`. If a provider returns a classified subscription-authentication failure, complete the official uncaptured login flow with `auth-login`, then run `task resume` with the same root, task ID, live flag and authorization. Authentication waiting does not reset budgets or repeat a completed sibling.

The two-worker interface is fully fixture-tested. Its first bounded live attempt at `b22020c` proved overlapping calls but blocked before integration on a narrow shell-runtime sandbox issue. That issue is corrected and host-canary-tested at `b9df1ad`; the corrected concurrent path has not yet completed a live verification/review cycle. Use live mode only under a separately declared budget and retain a failed checkpoint instead of automatically retrying.

`task status` groups implementation assignments as ready, active, waiting and completed. It also shows requested routes and reasons, total/provider/planning calls, elapsed allocation, token categories where reported, blockers and the next user action. A completed workflow stops at `awaiting_pr_approval`; the package records no publication approval and no push, PR, merge or deployment occurs.

## Routing configuration

The example registry uses verified account defaults and makes no exact-model, price or quality claim. Policies can select a profile by role, capability, difficulty, risk and optional node. An exact model loaded from JSON requires `availability`, `evidence_source` and a dated `evidence_date`. `unverified` and `unavailable` profiles cannot be routed. Relative evidence is optional; without it, the configured default is used and is not described as cost-optimal.

Requested provider/model/effort is durable controller data. Provider-reported model/effort is a separate nullable observation. The current contract accepts the installed Claude effort levels and rejects Codex effort because that CLI option is not part of the tested adapter.
