---
name: measured-optimisation
description: Evaluate performance hypotheses using a frozen representative benchmark and correctness gates before accepting an improvement.
---

# Measured optimisation

## Prerequisites

Identified workload/hardware, correct reference, fixed protocol, metric direction and bounded experiments.

Read the shared [authority and evidence rules](../../docs/skill-contract.md) before applying this procedure. They define the pack’s output and permission boundary. Load only a relevant [domain procedure](../../domains/README.md) if domain-specific verification is needed.

## Procedure

First demonstrate the harness detects the symptom and distinguishes contrasting workloads. Freeze workload identity, versions, warmup, repetitions, synchronization, statistic, noise threshold and correctness tolerances before evaluating candidates. Record a correctness-passing baseline.

Try one mechanism-based hypothesis at a time. Run correctness before measuring speed. Reject a faster candidate that violates correctness, memory or compatibility constraints. Record raw samples and accepted or rejected experiments, including no-change results. Never label an unmeasured hypothesis an improvement.

Compare repeated measurements on the same identified resources and record contention. Recheck selected winners on a protected final workload to reduce noise and benchmark overfitting. Do not tune against that final set. Preserve rejections so later work does not unknowingly repeat them. Restore only the experiment’s own changes when authorized; never reset unrelated work.

## Required output

Produce a version 1 `measured-optimisation` handoff using [the schema](../../contracts/handoff.schema.json) and [format guide](../../contracts/README.md). Payload fields: `protocol`, `baseline`, `experiments`, `correctness`, `decision`, `final_evaluation`. Record evidence, limitations and next actions in the envelope. Use empty lists only when nothing applies; use an explicit explanation for unavailable observations.

## Stop conditions

Stop at the declared time/attempt budget, unavailable hardware, failed correctness gate or target reached with adequate repeated evidence. No automatic publication, minimum iteration quota or indefinite plateau search.

## Attribution and adaptations

- [pstack / skills/poteto-mode/playbooks/hillclimb.md](https://github.com/backnotprop/pstack/blob/157aae39a733135e93d8b5b19ff62c6a84b0ad56/skills/poteto-mode/playbooks/hillclimb.md): Freeze protocol, retain rejects; remove automatic PR, minimum attempt floor, model IDs and unbounded plateau pushing.

See [retained notices](../../THIRD_PARTY_NOTICES.md). No upstream executable or linked plugin is required.
