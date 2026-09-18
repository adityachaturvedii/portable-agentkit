# Local PR approval package

Correct arithmetic total implementation in the disposable fixture.

- Base: `bb3265e847051b69ac69bffcacb5c2661e737495`
- Head: `eb94e4b8091aba4eb8154b4ee933c1917424f108`
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
