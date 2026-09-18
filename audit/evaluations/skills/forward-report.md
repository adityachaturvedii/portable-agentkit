# Synthetic forward evaluation

Applied task-contract, system-investigation, interface-design, change-impact, behavioral-testing, fault-diagnosis, browser-verification and delivery-evidence. Read catalog, each selected skill, shared skill contract, schema/format examples, backend and frontend procedures. Performance optimisation has no trigger. No independent-review handoff was produced: this evaluator implemented the invoice change and cannot claim a separate reviewer identity.

Created a dedicated disposable Git repository and worktree before implementation. Base: 43f9607c1830fb374886bbbdbb00188b0a41e50c. Red tests revision: 340549c566b6e70b5cf1516d0f5b088ef97c1221. Candidate: 0f2fd97567a2840c3698a17186ccebb0c3360703. Branch: fix/invoice-promotion. Worktree: /private/tmp/agentkit-forward-test/invoice-worktree. Original baseline source remains in project. No toolkit file was edited. Git identity was synthetic and set only through subprocess environment; global configuration was disabled.

Three local experiment runs used, of eight allowed: red unittest, shipping-only discriminating probe, green unittest. Red correctly reproduced 2250 versus expected 2300; changing only shipping from 0 to 500 increased total by only 450. The fix discounts/floors merchandise then adds shipping and validates prohibited ranges. Six test methods pass, including six invalid-range subcases, 0%/100% boundaries, empty merchandise, fractional-cent flooring and input nonmutation. Raw logs are under evidence/. Script execution took 1.333 seconds; whole agent wall time/model compute was not instrumented and is not falsely reported as measured usage.

All eight handoffs pass `python3 -m agentkit validate <individual JSON path>` from the toolkit cwd. Exact argv, exit codes and outputs are in evidence/validation.json. Six procedures are complete. Browser verification is blocked because no checkout origin/build/browser/separate verifier was supplied. Delivery remains incomplete because checkout acceptance is blocked. No external calls, publication, user repositories, credentials, plugins, GPU, paid APIs or subagents were used.

Observed instruction/schema friction:

1. All examples are empty blocked templates. Constructing real evidence and passing acceptance requires inspecting the full schema. A filled synthetic red/green example would reduce this burden without claiming production success.
2. contracts/README.md calls the evidence argument field `argv`, while the actual schema requires `command`. Used `command`; raw logs use descriptive `argv`. Clarify this naming discrepancy.
3. `python3 -m agentkit validate <directory>` fails with IsADirectoryError-style user output; individual file validation works. Directory support or explicit file-only usage would improve a multi-handoff workflow.
4. Backend procedure tells any backend contract change to exercise disposable databases/transactions, even for this pure function with no database. Treated irrelevant database checks as not applicable; this qualification should be explicit.
5. Separate compute/model/wall/cost budget instructions exceed the task-contract budget schema (max_attempts/max_wall_seconds/paid flag). Unknown model usage and representation limits were recorded in unknowns/limitations; delivery usage remains null.
6. Handoff case IDs can map to contract IDs only by convention; the validator does not link separate handoffs or prove every contract criterion appears in delivery. This run manually preserved AC1-AC5.
7. No instructions specify the canonical environment digest contents. This run hashes evidence/environment.json containing Python version, platform, executable and standard-library dependency note; the digest is reproducible from that artifact, not an assertion of hermetic execution.

The useful safety behavior held: absent browser capability produced a blocked artifact with no fabricated observations, and incomplete delivery validated without being misrepresented as approval. Validation explicitly says authority none and claims unauthenticated.

Process limitation: technical decisions and tests were made before implementation, but the formal JSON contracts were assembled after the code/evidence to fit the short evaluation. This checks practical handoff usability, not proof that a controller enforced procedure order or identity separation.
