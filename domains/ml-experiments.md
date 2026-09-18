# Ml experiments

Trigger: A change to data preparation, model selection or experiment conclusions.

1. Record data and split identity, preprocessing fit boundary, excluded samples and held-out membership. Check duplicate entities and temporal leakage before interpreting a metric.

2. State a falsifiable hypothesis and compare against a declared baseline with the same split, metric and resource allowance. Record seeds, configuration and checkpoint provenance.

3. Preserve raw per-run metrics and uncertainty appropriate to sample size; separate selection data from final evaluation. A single successful run is not statistical superiority.

Stop: Dataset access, leakage evidence or necessary baseline missing; mark conclusions incomplete.

Output: add the relevant checks, identities and evidence to the parent skill handoff; record missing capabilities in limitations. This procedure supplies requirements, not an installed tool or tested execution adapter.
