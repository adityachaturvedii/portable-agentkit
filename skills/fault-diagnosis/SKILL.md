---
name: fault-diagnosis
description: Diagnose a reproducible defect or regression through competing hypotheses and discriminating experiments.
---

# Fault diagnosis

## Prerequisites

Exact observed symptom, identified revision/environment, bounded experiment allowance and authorized data.

Read the shared [authority and evidence rules](../../docs/skill-contract.md) before applying this procedure. They define the pack’s output and permission boundary. Load only a relevant [domain procedure](../../domains/README.md) if domain-specific verification is needed.

## Procedure

Construct a red-capable reproduction that measures the reported symptom. Minimize one factor at a time while retaining it. A failure to start the test environment is infrastructure failure, not reproduction of the bug.

Keep competing falsifiable hypotheses and predict the observation each would produce. For slow training/GPU workloads, use a justified smaller case or checkpoint replay and record what it cannot reproduce. For intermittent failures, record attempts and failures, seeds/timing and changes to reproduction rate; a single clean run does not prove a fix.

Change one discriminating variable per experiment. Record the result, rejected hypotheses and remaining uncertainty. Tag temporary instrumentation for removal and keep secrets out of logs. Code inspection may form a hypothesis while execution is blocked, but cannot establish a reproduced root cause.

When a fix is authorized, preserve the regression at the public seam, rerun the original scenario and report the causal explanation with evidence. Escalate access only when the missing observation matters.

## Required output

Produce a version 1 `fault-diagnosis` handoff using [the schema](../../contracts/handoff.schema.json) and [format guide](../../contracts/README.md). Payload fields: `symptom`, `reproduction`, `hypotheses`, `experiments`, `root_cause`, `regression`. Record evidence, limitations and next actions in the envelope. Use empty lists only when nothing applies; use an explicit explanation for unavailable observations.

## Stop conditions

Stop after the declared attempt/time limit or repeated identical failure; preserve the attempt history across handoffs. Return blocked when the environment is missing and incomplete when the cause remains unresolved.

## Attribution and adaptations

- [matt-skills / skills/engineering/diagnosing-bugs/SKILL.md](https://github.com/mattpocock/skills/blob/74ca5fe077456a0b3b2f5310cf9430999fd0b5fd/skills/engineering/diagnosing-bugs/SKILL.md): Reproduction and competing hypotheses; allow bounded slow/intermittent experiments and blocked outcomes; omit HITL shell script.

See [retained notices](../../THIRD_PARTY_NOTICES.md). No upstream executable or linked plugin is required.
