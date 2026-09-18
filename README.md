# Portable Agentkit — skill foundation and CLI feasibility

A standalone toolkit with ten curated procedures, seven domain references, versioned contracts, source attribution and disposable validation fixtures. Phase 2 adds CLI diagnosis, bounded integration adapters and a narrow trusted disposable-workspace execution mode on the tested macOS host.

## Use from a checkout

Python 3.9 or newer; standard library only. No installation or configuration changes:

```sh
python3 -m agentkit list
python3 -m agentkit select diagnose
python3 -m agentkit show fault-diagnosis --domain backend-database
python3 -m agentkit validate contracts/examples/fault-diagnosis.json
python3 -m agentkit check
python3 -m unittest discover -s tests -v
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
| Durable controller, protected approvals, budgets, Git broker and cross-provider orchestration | Planned Phases 3–4; unavailable |
| Browser automation, CUDA/GPU worker, GitHub publication, installer/update | Not implemented; separate later gates |

The procedures describe desired engineering behavior. They are not enforcement of authenticated roles, monetary ceilings or publication permissions. Git worktrees are not sandboxes. Unattended untrusted execution is unsupported. Managed Linux/WSL2/Windows execution has not been validated; the current guard is macOS-specific.

## CLI integration scope

`python3 -m agentkit doctor` reports installed versions, advertised flags, CLI-reported authentication and sandbox initialization without inference or global setting changes. Unknown capability/billing data stays unknown. The diagnostic guard may be unavailable inside another sandbox; no automatic fallback occurs.

`python3 -m agentkit.sandbox_probe` uses disposable fake credentials and loopback canaries, without inference. Native probing needs a context that permits sandbox initialization. Read the [sandbox matrix](docs/sandbox-matrix.md) for effective limits.

The explicit `smoke` command runs only a fixed synthetic integer-sum task. `execution-check` creates a broken disposable source fixture, lets one CLI edit it and run its test, then applies an independent controller oracle. Without `--authorize-subscription-smoke`, either live command records a blocked result. The authorization switch is for a trusted operator and is not an authenticated approval system. Do not include live tests in ordinary CI. The parent of every fresh result directory must exist.

`boundary-check` and `lifecycle-check` are offline fake-canary checks for the exact owned-code filesystem profile and local process-group timeout/cancellation. The owned-code mode is limited to trusted controller-created disposable workspaces. It does not isolate tool traffic from provider traffic or prove access denial for every real credential path.

See [adapter contracts](docs/runtime-contracts.md), [original Phase 2 report](docs/phase2-validation-report.md), [execution follow-up](docs/phase2-execution-followup.md) and [sandbox matrix](docs/sandbox-matrix.md). Phase 3 may begin for the tested trusted disposable-workspace mode only.

## Inspect the work

- [Implementation checklist](docs/checklist.md), [decision log](docs/decisions.md), [phase requirements](docs/requirements.md), [threat model](docs/threat-model.md)
- [Source audit](docs/source-audit.md), [exact pins](audit/sources.lock.json), [attribution and notices](THIRD_PARTY_NOTICES.md)
- [Shared skill contract](docs/skill-contract.md), [handoff formats](contracts/README.md), [domain procedures](domains/README.md)
- [Validation report](docs/validation-report.md), [local PR proposal](docs/pr-proposal.md)
- [Phase 2 validation](docs/phase2-validation-report.md), [execution follow-up](docs/phase2-execution-followup.md), [sandbox matrix](docs/sandbox-matrix.md), [CLI source/compatibility review](docs/cli-source-review.md)
- [Original implementation specification](docs/implementation-spec.md)

The user authorized private GitHub publication on 2026-09-19: [adityachaturvedii/portable-agentkit](https://github.com/adityachaturvedii/portable-agentkit). All three phase branches are preserved; `implementation/phase-2` is the default branch for the latest work. No PR or merge is authorized by that publication request. Earlier validation records describe the local-only state at their recorded dates. Upstream MIT notices cover adapted material; an outbound license for original toolkit code will be chosen before broader distribution.
