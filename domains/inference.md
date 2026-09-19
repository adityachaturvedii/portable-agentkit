# Inference

Trigger: An inference backend, batching, caching or serving performance change.

1. Define output parity and tolerances before timing; include representative sequence/batch sizes and failure cases.

2. Measure warm and cold latency separately, representative concurrency and throughput, tail latency, memory peaks and load generation overhead.

3. Test cancellation, overload and cache invalidation; record model/tokenizer/checkpoint identities and whether output is deterministic.

Stop: Parity fails, model/data identity missing, or load is not representative enough to support the claim.

Output: add the relevant checks, identities and evidence to the parent skill handoff; record missing capabilities in limitations. This procedure supplies requirements, not an installed tool or tested execution adapter.
