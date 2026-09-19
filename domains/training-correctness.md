# Training correctness

Trigger: A change to loss, gradients, precision, optimizer, resume or distributed training.

1. Overfit a small synthetic dataset before scaling. Check finite loss and gradients against a known reference or finite differences with justified tolerances.

2. Record dtype, scaling, accumulation, clipping and optimizer state; verify checkpoint/resume behavior including RNG, scheduler and data position where needed.

3. Check distributed invariants only if affected. State determinism limits; CPU scalar checks cannot verify GPU mixed precision or multi-rank behavior.

Stop: Required framework/device/distributed environment unavailable, divergence unexplained or gradient/reference mismatch.

Output: add the relevant checks, identities and evidence to the parent skill handoff; record missing capabilities in limitations. This procedure supplies requirements, not an installed tool or tested execution adapter.
