# Cuda kernels

Trigger: A CUDA implementation or kernel performance claim.

1. Identify actual GPU, driver, CUDA/compiler/framework, shapes, strides, alignment, dtypes and numerical tolerances. Use an independent reference including noncontiguous and edge shapes.

2. Check memory safety and races with the appropriate available tools. Report unavailable sanitizers as missing checks. CPU reference agreement alone is not CUDA verification.

3. Require correctness before speed; synchronize device work, declare warmup and repetitions, record raw timings and exclusive GPU access. Validate selected winners on held-out workloads.

Stop: No verified GPU capability/lease, failed correctness/memory check, or exhausted budget. Do not connect to a worker or install tooling implicitly.

Output: add the relevant checks, identities and evidence to the parent skill handoff; record missing capabilities in limitations. This procedure supplies requirements, not an installed tool or tested execution adapter.
