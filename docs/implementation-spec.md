# Portable Agent Engineering System

Implementation plan for Aditya Chaturvedi · 18 September 2026 · Version 1

Status: researched design and implementation backlog. No personal repositories were accessed, no CLI installations were changed, and no remote GPU connection was made. Proposed defaults below are engineering choices to validate, not proven performance claims.

## 1. Objective and requirements

Build one versioned toolkit that works across machines and projects, using authenticated Claude Code and Codex CLIs. It must support deep learning, training, applied ML, inference, CUDA optimisation, backend services, databases, enterprise LLM and graph systems, and occasional frontend work.

The user interacts principally with a chief of staff. Managers, a tech lead, specialists and independent reviewers carry out bounded work. The system must produce inspectable evidence, control resource consumption, isolate execution and preserve human control over PR creation and merging.

Non-negotiable requirements:

- No user repositories are required during development or evaluation. Use disposable synthetic projects.
- Configure the toolkit once; discover machine capabilities on installation; configure project commands without rebuilding orchestration.
- Every implementation task begins on a new branch in a dedicated worktree. Never modify the user's current working tree or silently stash their changes.
- Present a completed local change and proposed PR before asking for the user's nod. Create the PR only after that approval. Merge requires separate authority.
- Use both providers where they improve outcomes. Keep logical roles independent of model IDs.
- Enforce bounded retries, budgets, sandboxing and permission separation in code, not just prompts.
- Maintain durable task state and provenance. Treat unavailable verification as incomplete, never passed.
- Keep the remote Linux RTX 4000 Pro Blackwell 24 GB machine an optional GPU worker. Verify actual device and software capabilities at connection time.

## 2. Research and design implications

The sources are public engineering write-ups, official documentation and source repositories. They do not establish private practices at OpenAI, Anthropic, SpaceX or xAI. No video-only claims are relied on.

| Source | Relevant finding | Our decision |
|---|---|---|
| [Lauren Tan / pstack](https://github.com/backnotprop/pstack) | Investigation, interface design, impact analysis, multi-model challenge and measured optimisation are explicit workflows. | Adapt selected procedures; replace host-specific delegation with toolkit adapters. |
| [Matt Pocock / skills](https://github.com/mattpocock/skills) | Small composable skills cover requirements, design, behavioral tests and diagnosis. | Use focused procedures; reduce repeated interviews and tracker-specific assumptions. |
| [Garry Tan / gstack](https://github.com/garrytan/gstack) | Planning, code review and browser QA are distinct activities with delivery-oriented handoffs. | Borrow review and QA procedures; keep publication and merge powers in the controller. |
| [Mitchell Hashimoto / adoption journey](https://mitchellh.com/writing/my-ai-adoption-journey) | Bounded tasks and executable feedback improve agent usefulness; recurring failures should inform the harness. | Maintain a regression corpus for the toolkit and add checks when failures justify them. No standalone Hashimoto skill library is assumed. |
| [Anthropic / building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Routing, parallelisation and evaluator loops have distinct uses; added complexity should demonstrate value. | Start with a deterministic graph and activate extra roles only where needed. |
| [Anthropic / long-running harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Incremental progress, explicit requirements and durable handoff artifacts address failures across context windows. | Persist task contracts, revisions, evidence and next actions outside model sessions. |

Three corrections to earlier discussion are important. First, model diversity is an opportunity to find different errors, not proof of correctness. Second, a Git worktree is a collaboration mechanism, not a sandbox. Third, CLI usage observations may be delayed or incomplete; exact universal token caps cannot be promised.

## 3. Product shape and portability

Proposed implementation: a Python controller with typed contracts, subprocess-based CLI adapters, a transactional SQLite run store and content-addressed artifact files. Use explicit state transitions before introducing a graph framework. Python fits the intended ML tooling; a graph framework can be reconsidered if workflow complexity warrants it.

The graph is real executable control flow, not a diagram or a collection of role prompts. Model outputs propose actions; trusted controller code validates transitions and authorises effects.

| Layer | Contents | Ownership |
|---|---|---|
| Toolkit release | Skills, agent contracts, graph definitions, adapters, validators, tests | Versioned and updated explicitly |
| Machine profile | CLI versions, supported features, local authentication method, sandbox backend, optional worker endpoints | Local; contains secret references rather than secrets |
| Project profile | Base branch, build/test commands, environment recipe, relevant checks and risk overrides | Declarative; task code cannot weaken controller policy |
| Run state | Task DAG, revisions, execution records, budgets, approvals, artifacts and checkpoints | Controller-managed |

Initial support targets: macOS and Linux control planes; Linux execution containers and optional remote Linux GPU worker. Windows support starts through WSL2 only after testing. Identical capabilities on every OS are not assumed.

Installation must be idempotent, avoid overwriting unrelated CLI settings, record managed files and support rollback/uninstall. Updates are pinned and tested; no automatic pull of upstream skill changes into active runs. Bootstrap detects capabilities without reading or exporting credential contents. Unknown CLI features fail with an actionable compatibility result.

Proposed commands, not implemented commands: `agentkit doctor`, `agentkit init`, `agentkit run`, `agentkit status`, `agentkit pause`, `agentkit resume`, `agentkit approve-pr`, `agentkit report`, and `agentkit update`.

A machine move exports portable run artifacts and Git objects, not live SQLite files or authentication. Import checks schema versions, hashes and required capabilities. One controller owns a run; a lease and explicit handover prevent simultaneous controllers from creating duplicate effects.

## 4. Skill foundation, before agent orchestration

The shortlist is concrete, but adoption requires a file-level audit at a pinned commit. Review licenses, transitive references, scripts, hooks, install behavior, network access, secret handling and publication actions. Retain applicable notices. If reuse rights are unclear, link the source and implement an original procedure rather than copying it.

| Toolkit skill | Candidate source | Adaptation and required output |
|---|---|---|
| task-contract | Matt: grill-with-docs, to-spec | Scope, non-goals, acceptance criteria, interfaces, risk and budget. Resolve known questions from context; ask only material unknowns. |
| system-investigation | pstack: how, why | Execution paths and evidence-backed findings; hypotheses explicitly marked. |
| interface-design | pstack: architect | Caller contracts, state/data ownership, tensor/API/schema semantics and errors. |
| change-impact | pstack: blast-radius | Affected consumers and invariants, with concrete verification targets. |
| behavioral-testing | Matt: tdd | Independent expected results, public behavior tests, small vertical changes. |
| fault-diagnosis | Matt: diagnosing-bugs | Reproduction, competing hypotheses, experiments and root-cause evidence. |
| measured-optimisation | pstack: hillclimb playbook | Frozen benchmark protocol, correctness constraints and accepted/rejected experiments. |
| independent-review | pstack: interrogate; selected gstack review checks | Findings with location, severity, rationale and reproduction where possible. |
| browser-verification | gstack: qa-only | User-flow observations and artifacts from a separate verifier. |
| delivery-evidence | Original synthesis | Revision-bound evidence and a review-ready PR proposal; no implicit publication. |

Upstream behavior must not override toolkit permissions. In particular, remove sticky cross-task routing, unbounded orchestration, automatic posting, automatic merging, whole-bundle installation and unnecessary universal confirmation requirements. Preserve useful comments for numerical assumptions and invariants; do not adopt a blanket no-comments rule.

The actual [Matt TDD skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/SKILL.md) requires confirming test seams and rejects implementation-coupled assertions. Our adaptation accepts established project seams without repeatedly asking the user. The [to-spec skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/to-spec/SKILL.md) includes tracker publication and extensive user stories; our technical contract makes publication separate and uses the detail the task warrants. [Diagnosis](https://github.com/mattpocock/skills/blob/main/skills/engineering/diagnosing-bugs/SKILL.md) supplies the reproduction discipline, adapted for slow GPU workloads and intermittent failures.

Add domain packs incrementally:

| Pack | Verification requirements |
|---|---|
| ML experiments | Data/split identity, leakage checks, hypothesis, baseline, seeds, configuration, metrics, checkpoint provenance and uncertainty as appropriate |
| Training correctness | Small-data overfit, gradient and precision checks, checkpoint/resume, determinism limits, distributed behavior when affected |
| CUDA kernels | Independent reference, shapes/strides/dtypes, numerical tolerances, memory and race checks, synchronised repeated measurements on identified hardware |
| Inference | Output parity, representative loads, warm/cold latency, throughput, memory, concurrency and failure behavior |
| Backend/database | Contracts, transactions, retries/idempotency, concurrency, migration compatibility, query plans and recovery |
| Enterprise LLM/graphs | Held-out cases, retrieval quality, tool permissions, tenant isolation, malicious inputs, bounded transitions, checkpoint/resume and partial failures |
| Frontend | Critical user flows, accessibility and responsive checks proportionate to the change |

Each skill has a narrow trigger, prerequisites, expected artifacts, stop conditions and linked procedures. Supporting scripts are added when they make checks more repeatable. Skills are evaluated against the same task without the skill; verbosity or a longer checklist is not evidence of improvement.

## 5. Roles and authority

| Role | Owns | Cannot do |
|---|---|---|
| Chief of staff | User intent, priorities, consolidated status, decisions and approval package | Invent approval or expand permissions |
| Engineering manager | Task DAG, ownership, dependencies and budgets | Change acceptance criteria to make work pass |
| Tech lead | Technical contract, interfaces, integration and verification design | Waive failures without an explicit recorded disposition |
| Specialist engineer | Implementation in an assigned worktree | Modify other workers' worktrees, controller policy or approvals |
| Reviewer | Independent findings on an immutable candidate | Silently fix the reviewed snapshot or approve its own implementation |
| Verifier | Execute checks and produce evidence | Treat an agent's claimed pass as measured evidence |
| Release manager | Prepare PR, inspect CI and perform authorised GitHub actions | Open a PR before the user's nod or merge without separate authority |

Roles are activated at checkpoints, not kept in continuous conversation. A routine task can combine coordination roles in one call while preserving reviewer independence. Multi-component work gets an explicit manager and tech lead. Dedicated security or numerical reviewers activate for relevant risks.

Agent contracts include task ID, role, objective, input revision, allowed paths/tools, dependencies, acceptance criteria, resource allocation, output schema and escalation conditions. Results separate claims, findings and controller-observed evidence.

## 6. Graphs and bounded loops

Delivery graph: intake → inspect → contract → plan → isolated implementation → deterministic checks → independent review → integration verification → awaiting PR approval → publish PR → CI/review follow-up → awaiting merge authority → merge → confirmed cleanup.

Implementation/check/review failures return through diagnosis to the responsible worker. Budget exhaustion, unavailable capabilities, contradictory requirements or repeated failure lead to a checkpointed blocked state. Cancellation is a distinct terminal transition with process cleanup.

Use three execution modes:

- Routine: one implementer, relevant checks, one concise independent review of code changes. Avoid a separate architecture panel.
- Substantial: tech-lead plan, bounded specialist tasks, cross-provider review and integration checks.
- High consequence: stronger model floor, relevant domain reviewer, independently managed acceptance checks and rollout/recovery evidence.

Risk depends on failure consequences and uncertainty, not lines changed. Auth, tenant isolation, migrations and numerical algorithms can require the higher mode even for small diffs.

Proposed starting limits: two concurrent implementation workers; one reviewer; delegation depth one; two repair attempts before mandatory diagnosis/routing reconsideration. Repeated identical failures stop earlier. These are configurable initial values, not optimal constants. Persistent failure must not reset its attempt count by spawning a new child.

Optimisation graph: baseline → one hypothesis → correctness → benchmark → accept/reject → record → next hypothesis within budget. Keep a protected final evaluation set. Run selected winners again to detect noise and benchmark overfitting. Preserve rejected experiments as concise records rather than repeatedly rediscovering them.

Review disagreement produces a falsifiable question, reproduction or targeted experiment. It does not trigger indefinite model debate or majority voting.

## 7. Git, worktrees, PRs and approval

The trusted Git broker fetches the intended base and records its SHA. Each new work item gets a branch and worktree. Dependent tasks may branch from a declared parent task revision; they do not silently inherit another worker's unfinished state.

Before the user's nod, keep branches local by default. The approval package includes the diff summary, base/head SHA, tests, findings, resource report and proposed PR title/body. PR approval authorises pushing the identified branch and creating that PR. It does not authorise merging.

Approval is stored outside the editable worktree and bound to repository, branch, head SHA, action and validity window. A different head before publication invalidates that approval. Reconcile GitHub state before retrying publication so a timeout cannot create duplicate PRs.

After PR creation, routine repairs within approved scope may update it with fresh checks and recorded heads. Changes to scope, permissions, architecture or materially different behavior return for a decision. An in-flight merge approval becomes stale when the head changes. Check CI and branch protection on the current revision immediately before an authorised merge.

Use focused commits and diffs, project formatting, meaningful tests, lockfile consistency and checks for secret/generated-file inclusion. No force push to shared or protected branches. Never silently remove failed tests or weaken thresholds. Track changed tests and acceptance rules as review-sensitive changes.

Worktrees share repository metadata; official [Git worktree documentation](https://git-scm.com/docs/git-worktree) describes shared and per-worktree state. Consequently, workers must not get unrestricted write access to the common Git directory. The broker owns Git mutations, uses argv-based commands, validates refs and paths, and disables untrusted hooks in privileged operations. Stronger execution boundaries use a sandbox copy of the task tree and return a patch to the broker. Every accepted patch is path-validated, committed to its assigned branch and reverified.

Integration belongs to one owner. Combine selected commits in an integration worktree and re-run affected checks. Cleanup requires confirmed merge/preservation, no active lease and no uncommitted user work. Abandoned work is archived or explicitly discarded, never guessed safe to delete.

## 8. Claude Code and Codex integration

Both engines expose documented programmatic interfaces: [Codex noninteractive mode](https://learn.chatgpt.com/docs/non-interactive-mode) provides JSON events and schema-constrained output; [Claude Code programmatic execution](https://code.claude.com/docs/en/headless) provides structured and streaming output. Build separate adapters and validate the installed versions before relying on a flag.

Normalised operations: capability detection, start, event consumption, result parsing, session continuation where supported, cancellation and usage reconciliation. Persist provider session IDs as optional accelerators. Portable artifacts, not a provider session, are the source of truth for cross-provider continuation.

Use documented CLI authentication. Do not extract subscription tokens to call undocumented APIs. Do not assume a subscription includes arbitrary API/SDK usage. Authentication mode and any credit-based overflow must be surfaced in doctor output. No automatic switch to API billing or paid overflow.

Default cross-provider use: implementer on one engine, substantial-change reviewer on the other. Difficult diagnosis may transfer engines after bounded attempts. Two parallel solutions are reserved for explicit uncertainty where an experiment can choose between them. Provider-native subagents remain bounded leaf workers until their permissions, usage attribution and cancellation are verified. No uncontrolled nested fleets.

Potential host configuration, hooks, MCP servers and skills are part of the execution environment. The adapter must enumerate or constrain what gets loaded; a managed toolkit directory must not indiscriminately inherit unrelated plugins. [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills) is a compatibility reference, not evidence that every Claude-specific skill feature ports unchanged.

## 9. Model routing and cost management

Begin with auditable routing rules. Learn routing improvements only after sufficient evaluation data. Do not hardcode provider stereotypes or silently use the strongest model for every management role.

Filter candidates by capability, available authentication, risk floor, context requirements and validated task performance. Among eligible candidates, minimise expected completion cost: initial usage + expected repairs + review + execution time + human interruption cost. Record the rationale, actual model/version and outcome.

| Task | Initial policy |
|---|---|
| Status formatting, log extraction | Efficient validated model, or deterministic code |
| Routine implementation | Balanced validated coding model |
| Architecture, subtle concurrency, numerical correctness | Strong reasoning model from the start |
| Substantial independent review | Suitable model from the other family |
| Tool execution and release eligibility | Deterministic controller and tests |

Budgets exist per run and per period. Child allocations reserve from the parent ledger before launch; accounting is atomic so concurrent children cannot each spend the same balance. Keep a verification reserve, initially 25% of the task allocation, subject to evaluation. At 80% projected consumption, stop adding optional work and prioritise verification. At exhaustion, checkpoint rather than reduce required quality gates.

Track input/output/reasoning/cache usage when reported, provider calls, model identity, wall time, retries, GPU time and billed versus estimated money. Missing fields remain unknown. Never compare token counts across providers as an exact equivalent measure of work.

Subscription allowance, API dollars and compute cost are separate ledgers. Claude's [cost documentation](https://code.claude.com/docs/en/costs) explicitly distinguishes subscription usage from session cost estimates. Remaining plan quota may not be programmatically accessible; report telemetry freshness and uncertainty rather than inventing a percentage.

Hard controls include maximum process lifetime, maximum launched calls, concurrency and compute quotas. Token/spend ceilings are exact only where the provider exposes and enforces them. With delayed reporting, use conservative reservations, bounded calls and early cancellation; disclose possible in-flight overshoot. No toolkit can promise exact provider billing enforcement solely from post-call telemetry.

Reduce context through progressive skill loading, scoped file retrieval, bounded logs, evidence references and compact handoffs. Keep decisions, failures and unresolved hypotheses in durable state. Reuse evidence only when the relevant code, dependency, environment, data and test identities still match. Cross-project memory is opt-in and must not leak proprietary information.

## 10. Safety architecture

Trust boundaries: user → trusted controller/Git broker → CLI engine → tools and execution sandbox → project code. LLM output, repository instructions, dependencies, logs and external content cannot grant permissions. Project configuration can request capabilities but cannot lower controller-enforced limits.

Native CLI protections are useful but must be validated. [Codex security documentation](https://learn.chatgpt.com/docs/security) and [Claude sandbox documentation](https://code.claude.com/docs/en/sandboxing) describe their controls. Claude documents explicit no-unsandboxed-retry and fail-if-unavailable settings; default access must not be assumed sufficient for credential protection.

Separate two profiles:

- Owned-code development: verified native CLI sandbox plus constrained subprocess execution and isolated tests. Report residual host exposure honestly.
- Untrusted execution: dedicated container/VM worker with no host credentials, restricted egress and a brokered artifact interface. Potentially hostile code requires a stronger boundary than an ordinary shared-kernel container.

Credential isolation with subscription CLIs is a phase-one feasibility gate. If the CLI can read authentication files, shell tools must still be prevented from reading them. Prove the actual effective boundary with canary secrets. If safe separation cannot be achieved for a given platform/authentication mode, do not enable unattended untrusted execution there. Do not describe an unimplemented credential proxy as a solved capability.

No host Docker socket, unrestricted home mount, agent socket forwarding or production credentials. Privileged setup is a separate explicit operation. Dependency fetching happens in a restricted setup stage; dependency install scripts are also untrusted execution. Network allowlists do not by themselves prevent exfiltration through an allowed endpoint, so accessible data and secrets must also be minimised.

Use filesystem protections that cover symlinks, path traversal and sibling worktrees. Protect state, approvals, verifier fixtures and policy files from workers. Logs are redacted, access-controlled and retained under a configurable policy. Record actions and artifacts; do not require private chain-of-thought traces.

Sandbox escape, credential access or authority bypass attempts halt the relevant run and preserve evidence. Infrastructure failure, test failure and quality failure are different statuses. Cancellation kills process groups and reconciles remote job termination before releasing leases.

## 11. Optional remote GPU execution

Use a configured worker endpoint with an unprivileged account and verified host identity. Do not forward the user's SSH agent or copy model credentials to the GPU worker. The controller submits an identified code/environment bundle and receives job IDs, logs and artifacts.

Record hardware, driver, CUDA/compiler/framework versions, dataset identifiers, seeds and commands. Enforce exclusive GPU leases for performance comparisons. Shared training/inference use requires an explicit scheduling policy. A 24 GB device constrains experiment size; use declared memory requirements and preflight checks rather than assuming every architecture fits.

Jobs need wall-time limits, heartbeats, explicit cancel/query operations and checkpoint handling. A network disconnect must not launch a duplicate training job. Reconnect by idempotency key and job ID. No new jobs while the controller cannot reconcile outstanding allocations. Quota enforcement must continue remotely if the local machine disconnects.

GPU device access exposes a driver boundary; a container with GPU access is not complete protection against hostile kernels. Enable the appropriate execution profile and retain this residual risk in worker capability reporting.

## 12. Evidence and recovery contracts

Core records:

- TaskContract: objective, scope, acceptance checks, risk, budget, base revision and dependencies.
- AgentAssignment: role, model/provider, worktree, allowed capabilities and allocated budget.
- ExecutionRecord: controller-observed command, environment digest, start/end, exit status and artifact hashes.
- ReviewFinding: revision, location, severity, explanation, reproduction and disposition.
- Approval: user identity, action, repository, head SHA and validity.
- Checkpoint: completed actions, active jobs, next actions, failures and reconciliation requirements.

Use transactional state changes and an append-only event history. External effects use idempotency keys and reconcile-before-retry behavior. Exactly-once remote execution is not assumed. Recover safely from duplicate events, truncated CLI streams, missing usage, process death and controller restart.

A passed project test is useful evidence but not a guarantee: project code controls much of its own test execution. Distinguish self-reported assertions, controller-observed commands and independent fixture checks. Acceptance thresholds and protected fixtures live outside the implementation workspace. Testing is risk-based; do not demand meaningless tests for prose-only edits.

## 13. Implementation sequence and exit criteria

Skills are curated first. A small feasibility spike then proves that the proposed safety and CLI integration are practical before extensive orchestration work.

| Phase | Deliverable | Exit criterion |
|---|---|---|
| 0. Source audit and contracts | Pinned source inventory, license/dependency review, requirements and threat model | Each candidate marked adopt/adapt/reject; no undocumented executable dependencies |
| 1. Portable skill foundation | Core skill pack, initial domain procedures, structured handoff formats | Realistic synthetic tasks demonstrate correct triggers and useful outputs; no conflicting authority rules |
| 2. CLI and sandbox feasibility | Doctor command, both CLI adapters, sandbox probes, cancellation and auth-mode reporting | Both engines complete a disposable task; effective isolation and usage limitations documented |
| 3. Minimum delivery graph | Durable controller, task branch/worktree broker, implement/check/review loop, budgets, local approval package | Crash/restart retains work; denied actions remain denied; no PR before approval |
| 4. Cross-provider roles | Request/inventory planning, deterministic chief-of-staff and manager/tech-lead activation, two-worker scheduler, bounded specialists, explicit model router | Independent work overlaps without shared writes; dependencies, routing reasons, allocations and observed usage/cost are inspectable; required review stays independent |
| 5. Domain and GPU packs | ML/CUDA/inference/database/LLM fixtures, optional remote worker | Correctness gates precede benchmark acceptance; disconnect and duplicate-job tests pass |
| 6. GitHub and packaging | PR broker tested against fixtures, gated live disposable-repo validation, installer/update/rollback | No duplicate PRs; stale approvals rejected; clean installation and resume on another supported machine |
| 7. Calibrated release | Held-out evaluation report, failure corpus, compatibility matrix and documented limits | Workflow quality and intervention metrics justify added complexity over a single-agent baseline |

Do not make autonomous merging, a dashboard, a vector database, a fleet scheduler or a learning-based router prerequisites for the first release. Add them only when a demonstrated need warrants them. Use ordinary persisted DAG dependencies before building a general code knowledge graph.

## 14. Evaluation plan

Build disposable projects with planted defects and independently maintained expected outcomes. Start with roughly 18 tasks spanning backend, database, training, inference, numerical kernels, LLM graphs, frontend and orchestration recovery. CPU fixtures run everywhere; GPU-required cases are reported separately and never marked passed without hardware.

Compare four conditions on matched tasks and resource allowances: native single-agent baseline, skills-only, skills plus deterministic graph, and cross-provider review. Use repeated runs for noisy comparisons and record model/tool versions. Separate development cases from held-out cases; do not claim statistical superiority from a handful of successes.

Measure acceptance against independent checks, escaped defects, review precision/recall for planted defects, repair cycles, human interventions, completion time, usage and compute. Measure useful outcomes per resource unit, not lines of code or number of agents.

Required regression scenarios include: prompt injection cannot authorise PR creation; sibling worktree and common Git metadata writes are blocked; canary secrets are inaccessible; unauthorised egress is blocked; stale approvals fail; duplicate effects are reconciled; budget reservations survive concurrency; changed code invalidates evidence; controller restart preserves state; remote cancellation is confirmed; a worker cannot self-approve its checks.

Critical boundary tests must all pass on each advertised platform. Any unverified boundary is a documented unsupported mode, not an implied guarantee. Model quality thresholds are set per fixture family after baseline measurement. A new model or skill release is canaried before becoming the default.

## 15. Human involvement and completion criteria

The chief of staff should bring the user only material requirement ambiguities, consequential design trade-offs, genuine access/budget exceptions and the finished PR approval package. It should include a recommended choice and consequences, not forward raw agent chatter. Independent work can continue while one decision is pending.

Routine coordination, reversible implementation, diagnosis and verification stay autonomous within scope. The user can inspect state, pause, cancel or change priorities at any time. No role can reinterpret silence as approval.

The first release is complete when a clean supported machine can install the toolkit, detect available engines, run a synthetic task in isolation, produce independent verification, pause/resume, report resource consumption and prepare a local PR proposal without contacting a personal repository. Optional GitHub and GPU integrations have separate acceptance gates.

The next implementation action is Phase 0: freeze source revisions, complete the skill audit and write the portable skill contracts. No additional repository selection is needed from the user.
