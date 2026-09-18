# Independent toolkit review

Reviewed immutable candidate `dfe59c52a9bce4d83d3cdfeeec9d4010f8ef305c`. The reviewer did not author toolkit code; prior synthetic invoice implementation is a separate artifact. No toolkit changes were made. Parent changes during the review were excluded; final validation uses a local `git archive` snapshot of the exact commit.

## Findings

1. **Medium — complete optimisation can explicitly remain incomplete.** `agentkit/validation.py:203` checks only accepted decisions. A handoff with `status=complete`, `decision=incomplete`, `correctness=not_run` and empty evidence validates successfully. Reproduce with `python3 -m agentkit validate /private/tmp/agentkit-toolkit-review/probe-complete-optimisation-incomplete.json`. Complete procedures should require a terminal decision. A rejected candidate with failed correctness is a valid completed evaluation and should remain supported.
2. **Low — findings review can contain zero findings.** `agentkit/validation.py:188` rejects no-findings with nonempty findings, but accepts the converse: `verdict=findings`, `findings=[]`. Reproduce with `python3 -m agentkit validate /private/tmp/agentkit-toolkit-review/probe-findings-verdict-empty.json`. Require at least one finding for that verdict.

Both are observable structural contradictions, not requests to authenticate prose, identities, hashes or cross-document facts. They do not create publication authority.

## Checks and optimisation forward task

All 25 existing tests and pack check passed before subsequent parent edits. JSON formats reject unknown properties/versions, self-report measured passes, stale evidence, and explicit failed correctness accepted as optimisation. Runtime source uses the standard library, executes no handoff commands, does not follow evidence artifact paths and exposes no publisher/provider operation. Dependency and authority limitations in docs are appropriately narrow. The relocation test passed with spaces in the path and an empty home directory; this does not establish Linux/WSL portability.

For the optimisation forward test, fixed integer summation workloads, two warmups, seven repetitions, median nanoseconds, a 20% noise threshold and exact integer correctness were recorded before measurements. A correct loop baseline matched six independently worked sums and was timed on contrasting workload sizes. The purported faster constant-time candidate omits the final summand: n=2 returns 0 instead of 1. The independent gate exits 1. Following the skill, candidate timing and final winner evaluation were not run. The rejected handoff validates; changing failed correctness to an accepted decision is rejected with exit 2. Thus the guidance and explicit failed-correctness guard work; the unrelated complete/incomplete state omission remains.

`independent-review.json` and `measured-optimisation-rejected.json` are the useful versioned handoffs. `immutable-validation.json` binds final validation commands/results to the exact snapshot. `optimisation-protocol.json`, `optimisation-raw.json`, `candidate-gate.txt`, `probe-results.json`, `unittest.txt` and `pack-check.txt` retain raw evidence. No speed improvement is claimed, because a failed correctness gate prevented candidate timing. No network, provider, GPU, plugin, user repository or global configuration access occurred.
