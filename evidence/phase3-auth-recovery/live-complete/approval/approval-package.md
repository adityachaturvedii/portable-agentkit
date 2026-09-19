# Local PR approval package

Correct arithmetic total implementation in the disposable fixture.

- Base: `9ac4d45200c55b3c3f2876f0f0ad1ab19a88cf26`
- Head: `873e3a2306f28c3bf61849b96f80fba119297b9d`
- Branch: `agentkit/phase3-demo`
- Status: `awaiting_pr_approval`

## Proposed PR

**Fix disposable arithmetic total**

Correct `total` to add its operands. Verified with the immutable unittest suite and independent review.

## Diff

```diff
diff --git a/calculator.py b/calculator.py
index 1fcbd09..06164e9 100644
--- a/calculator.py
+++ b/calculator.py
@@ -1,3 +1,3 @@
 def total(left, right):
     """Return the arithmetic sum."""
-    return left - right
+    return left + right
```
