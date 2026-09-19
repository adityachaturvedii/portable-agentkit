# Portable Agentkit — skills, bounded CLI adapters and durable local delivery

A standalone toolkit with ten curated procedures, seven domain references, versioned contracts, source attribution and disposable validation fixtures. Phase 2 adds CLI diagnosis and a narrow trusted disposable-workspace execution mode on the tested macOS host. Phase 3 adds transactional local delivery and authentication recovery. Phase 4 adds validated task intake, selective role graphs, account-default provider routing, separate quality reserves and a task-oriented terminal interface for controller-created disposable fixtures.

## Use from a checkout

Python 3.9 or newer; standard library only. No installation or configuration changes:

```sh
python3 -m agentkit list
python3 -m agentkit select diagnose
python3 -m agentkit show fault-diagnosis --domain backend-database
python3 -m agentkit validate contracts/examples/fault-diagnosis.json
python3 -m agentkit check
python3 -m unittest discover -s tests -v
python3 -m agentkit controller-demo --output /tmp/agentkit-phase3-demo
python3 -m agentkit auth-status claude
python3 -m agentkit task fixtures
python3 -m agentkit task submit --root /tmp/agentkit-task --task-id demo \
  --fixture calculator --request "Repair the calculator fixture"
python3 -m agentkit task plan --root /tmp/agentkit-task --task-id demo
python3 -m agentkit task start --root /tmp/agentkit-task --task-id demo
python3 -m agentkit task status --root /tmp/agentkit-task --task-id demo
python3 -m agentkit task package --root /tmp/agentkit-task --task-id demo
```

Run these commands from this directory. To move machines, copy the entire directory, preserving relative paths. For a clean source copy, use `git archive HEAD` after committing. Skills link to shared contracts and notices, so copying a single SKILL.md is insufficient. Relocation is tested; installation, CLI skill auto-discovery and rollback are later work.

`select` takes an explicit intent from `list`; it is not natural-language routing. `show` emits the chosen skill, shared rules, format guide and optional domain procedure for an authorized host to consume. Read the linked schema when producing JSON. `validate` accepts one file, returns exit 0 on structural/consistency success and exit 2 on invalid input. A valid document grants **no authority** and does not prove its claims. Helpers never run command strings or follow evidence paths in a handoff.

## What exists

| Capability | Status |
|---|---|
| Pinned source inventory, adaptations, MIT notices, dependency exclusions | Implemented; hashes checked against downloaded snapshots |
| Ten core skills, seven initial domain procedures | Implemented; all ten exercised across synthetic task, review and optimisation cases |
| Offline discovery, rendering, strict JSON handoff validation | Implemented and tested on macOS / Python 3.9.6 |
| CPU defect fixtures and native-baseline comparison | Tested development cases; no general quality improvement established |
| Claude/Codex adapters, read-only doctor, bounded POSIX transport and cancellation | Implemented; both CLIs passed live disposable coding checks and independent acceptance |
| Sandbox boundaries / credential isolation | Explicit macOS workspace/protected-path canaries passed; comprehensive credential and tool-network isolation unsupported |
| Durable controller, protected approval records, budgets and controller-owned Git broker | Implemented and tested with deterministic adapters |
| Guided subscription-auth recovery | Implemented with uncaptured official CLI terminal handoff, durable stage checkpoint, bounded retries and revision/evidence revalidation |
| Cross-provider disposable delivery workflow | Deterministic path passes; the bounded live result is recorded in the current validation report |
| Phase 4 task CLI, selective role graph, routing and quality reserves | Implemented and fixture-tested for controller-created disposable tasks; general repository onboarding remains unsupported |
| Browser automation, CUDA/GPU worker, GitHub publication, installer/update | Not implemented; separate later gates |

The procedures describe desired engineering behavior. They are not enforcement of authenticated roles, monetary ceilings or publication permissions. Git worktrees are not sandboxes. Unattended untrusted execution is unsupported. Managed Linux/WSL2/Windows execution has not been validated; the current guard is macOS-specific.

## CLI integration scope

`python3 -m agentkit doctor` reports installed versions, advertised flags, CLI-reported authentication and sandbox initialization without inference or global setting changes. Unknown capability/billing data stays unknown. The diagnostic guard may be unavailable inside another sandbox; no automatic fallback occurs.

`python3 -m agentkit.sandbox_probe` uses disposable fake credentials and loopback canaries, without inference. Native probing needs a context that permits sandbox initialization. Read the [sandbox matrix](docs/sandbox-matrix.md) for effective limits.

The explicit `smoke` command runs only a fixed synthetic integer-sum task. `execution-check` creates a broken disposable source fixture, lets one CLI edit it and run its test, then applies an independent controller oracle. Without `--authorize-subscription-smoke`, either live command records a blocked result. The authorization switch is for a trusted operator and is not an authenticated approval system. Do not include live tests in ordinary CI. The parent of every fresh result directory must exist.

`boundary-check` and `lifecycle-check` are offline fake-canary checks for the exact owned-code filesystem profile and local process-group timeout/cancellation. The owned-code mode is limited to trusted controller-created disposable workspaces. It does not isolate tool traffic from provider traffic or prove access denial for every real credential path.

See [adapter contracts](docs/runtime-contracts.md), [original Phase 2 report](docs/phase2-validation-report.md), [execution follow-up](docs/phase2-execution-followup.md) and [sandbox matrix](docs/sandbox-matrix.md). Phase 3 may begin for the tested trusted disposable-workspace mode only.

`controller-demo` runs the complete Phase 3 path with deterministic implementer/reviewer adapters by default. It creates a disposable repository, task branch/worktree and worker copy; commits one allowed source change; runs controller-owned tests in a separate read-only/no-network verification copy; performs independent review; then writes a local approval package and stops at `awaiting_pr_approval`. The package records no approval and performs no publication. Read the [controller contracts](docs/controller-contracts.md), [Phase 3 validation report](docs/phase3-validation-report.md) and [corrective review](docs/phase3-review-findings.md). Live mode requires the explicit subscription-smoke flag and remains limited to the previously tested macOS profile.

When live execution reports missing or expired subscription login, the workflow stops at `authentication_required` after finalizing the failed call. Use `auth-login` in a real local terminal, then rerun `controller-demo` with the same output, live authorization and `--resume`. Login output is attached directly to the terminal and is never captured in evidence. If the controller ended while login was in progress, `auth-reconcile` requires explicit process evidence before another attempt. See [guided authentication recovery](docs/authentication-recovery.md) for Codex browser/device commands, Claude's manual code handoff, historical checkpoints, candidate validation and limitations.

## Phase 4 task interface

`task submit` accepts natural-language intent only for a named controller-created fixture. It records the original request separately from controller assumptions, validates scope, creates a proposed execution graph, selects audited skills by content hash and stops before execution. `task plan` shows that contract and graph. `task start` executes the deterministic fixture workflow by default; add both `--live` and `--authorize-subscription-smoke` only for the explicitly bounded subscription demonstration. `task status` reports the stage, active assignments, route reasons, reserves, observed usage, blocker and next action. `task cancel` prevents new launches. `task resume` resumes only a verified authentication checkpoint. `task package` reads the final local package and never publishes it.

The `calculator` fixture uses one implementer, verification and review. `text-metrics` and `inventory` use two isolated specialist worktrees, a controller-owned integration commit, verification and review. Chief-of-staff, tech-lead and manager responsibilities are deterministic controller functions in this phase, so routine tasks incur no management-model calls. Provider defaults are configurable at submission with `--implementer-provider` and `--reviewer-provider`; exact model, effort, relative cost and availability remain unknown until the installed CLI/account reports them. No model identifier or price is inferred.

The execution graph is bounded to two implementation subtasks, two repair cycles, two concurrent calls and twelve nodes. Verification and review each hold a separate call reserve. Output is bounded to 1 MiB per provider request; CLI-managed context remains unknown. Token categories, estimates and billed cost remain `null` when unavailable. See [role contracts](docs/phase4-role-contracts.md), [graph, routing and budget semantics](docs/phase4-graph-routing.md) and the [Phase 4 validation report](docs/phase4-validation-report.md).

## Inspect the work

- [Implementation checklist](docs/checklist.md), [decision log](docs/decisions.md), [phase requirements](docs/requirements.md), [threat model](docs/threat-model.md)
- [Source audit](docs/source-audit.md), [exact pins](audit/sources.lock.json), [attribution and notices](THIRD_PARTY_NOTICES.md)
- [Shared skill contract](docs/skill-contract.md), [handoff formats](contracts/README.md), [domain procedures](domains/README.md)
- [Validation report](docs/validation-report.md), [local PR proposal](docs/pr-proposal.md)
- [Phase 2 validation](docs/phase2-validation-report.md), [execution follow-up](docs/phase2-execution-followup.md), [sandbox matrix](docs/sandbox-matrix.md), [CLI source/compatibility review](docs/cli-source-review.md)
- [Phase 3 controller contracts](docs/controller-contracts.md), [Phase 3 validation](docs/phase3-validation-report.md), [archived evidence](evidence/phase3/manifest.json)
- [Guided authentication recovery](docs/authentication-recovery.md), [live completion evidence](evidence/phase3-auth-recovery/manifest.json)
- [Phase 4 role contracts](docs/phase4-role-contracts.md), [graph and routing](docs/phase4-graph-routing.md), [Phase 4 validation](docs/phase4-validation-report.md), [live evidence manifest](evidence/phase4/manifest.json)
- [Original implementation specification](docs/implementation-spec.md)

The user authorized private GitHub publication on 2026-09-19: [adityachaturvedii/portable-agentkit](https://github.com/adityachaturvedii/portable-agentkit). All three phase branches are preserved; `implementation/phase-2` is the default branch for the latest work. No PR or merge is authorized by that publication request. Earlier validation records describe the local-only state at their recorded dates. Upstream MIT notices cover adapted material; an outbound license for original toolkit code will be chosen before broader distribution.
