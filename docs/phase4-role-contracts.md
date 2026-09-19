# Phase 4 role contracts

The executable definitions are in `agentkit/phase4_contracts.py`. Roles describe responsibility; only implementer/repair and reviewer nodes require provider calls. The controller owns authority, scheduling, Git operations, evidence and approval state.

| Role | Inputs | Outputs | Allowed tools | Completion | Escalation |
|---|---|---|---|---|---|
| Chief of staff | User request, controller status | Validated intake, concise status, attention request | Controller read | Requirements and assumptions are separate; next action is explicit | Material ambiguity, authority/access/cost change or final approval |
| Tech lead | Validated intake, fixture contract | Decomposition, interfaces, acceptance design | Controller read | Bounded graph and immutable acceptance are recorded | Contradictory requirements or unsupported integration |
| Manager/coordinator | Validated graph, budget ledger | Dependency schedule, bounded allocations | Controller read | Dependencies, concurrency and quality reserves are valid | Capacity exhaustion or uncertain execution ownership |
| Implementer/specialist | One assignment, candidate revision, bounded feedback | Candidate changes, structured result | Owned code in one worker copy | Git broker accepts only declared paths into the owned worktree | Authentication, sandbox failure, failed acceptance or authority request |
| Verifier | Immutable candidate, controller acceptance test | Measured evidence | Local read-only/no-network Seatbelt profile in live mode | Candidate remains unchanged and acceptance passes | Missing sandbox, failed check or identity change |
| Independent reviewer | Immutable candidate, task contract, evidence references | Validated concrete findings | Model-only snapshot | No finding, or each material finding names an ID, path, criterion and defect | Authentication, unavailable required cross-provider review or unresolved finding |

Workers receive no controller authority object, database path, Git metadata or approval capability. A worker proposal to add tools, paths, network, publication, spending or another agent is untrusted data. The controller rejects it unless a separate trusted policy already authorizes it.

A routine calculator task activates no manager node and uses no planning model. A decomposed fixture activates a deterministic schedule, gives each specialist a separate branch/worktree and integrates only broker-validated disjoint paths. The manager remains a responsibility in the event history rather than an always-running agent.

Handoffs contain the task/node ID, objective, allowed paths, acceptance criteria, exact candidate revision, constraints and, for repair, only the applicable failed-test tail or validated review findings. They omit full transcripts, credentials and approval state.
