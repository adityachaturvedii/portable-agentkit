# Portable Agentkit — Phase 0 and Phase 1

A standalone, offline skill foundation for engineering agents. It includes ten curated procedures, seven domain references, versioned handoff formats, source attribution and disposable validation fixtures. No provider, plugin, project, credential or GPU connection is needed.

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
| Ten core skills, seven initial domain procedures | Implemented; eight skills exercised in a synthetic forward task |
| Offline discovery, rendering, strict JSON handoff validation | Implemented and tested on macOS / Python 3.9.6 |
| CPU defect fixtures and native-baseline comparison | Tested development cases; no general quality improvement established |
| Claude/Codex adapters, doctor, sandbox, cancellation, credential isolation | Planned Phase 2; unavailable |
| Durable controller, protected approvals, budgets, Git broker and cross-provider orchestration | Planned Phases 3–4; unavailable |
| Browser automation, CUDA/GPU worker, GitHub publication, installer/update | Not implemented; separate later gates |

The procedures describe desired engineering behavior. They are not enforcement of OS isolation, authenticated roles, monetary ceilings or publication permissions. Git worktrees are not sandboxes. Unattended untrusted execution is unsupported. Linux/WSL2 and provider integration have not been tested.

## Inspect the work

- [Implementation checklist](docs/checklist.md), [decision log](docs/decisions.md), [phase requirements](docs/requirements.md), [threat model](docs/threat-model.md)
- [Source audit](docs/source-audit.md), [exact pins](audit/sources.lock.json), [attribution and notices](THIRD_PARTY_NOTICES.md)
- [Shared skill contract](docs/skill-contract.md), [handoff formats](contracts/README.md), [domain procedures](domains/README.md)
- [Validation report](docs/validation-report.md), [local PR proposal](docs/pr-proposal.md)
- [Original implementation specification](docs/implementation-spec.md)

Changes remain local. There is no configured repository remote, push, PR or merge. Upstream MIT notices cover adapted material; an outbound license for original toolkit code will be chosen before distribution.
