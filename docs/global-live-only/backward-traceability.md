# Live-only lines from global backward-traceability (not in repo), saved 2026-11-01 before deploy
# Review and merge into skills/extensions/backward-traceability, then delete this file.
description: Make every number in the final PDF traceable to the exact code line that produced it. Uses \hypertarget/\hyperlink LaTeX commands and \num{formula} evaluated at compile time. Use for reproducibility and data integrity verification.
Triggers: /backward-traceability, трассируемость, reproducibility, number-to-code, PDF traceability.
triggers: [/backward-traceability, трассируемость, reproducibility, number-to-code, "PDF traceability"]
### Step 3: Use \num for Computed Values
For values derived from other values, use `\num{}` for compile-time evaluation:
```latex
% \num{formula, "explanation"} → evaluated at compile time
The improvement is \num{45.3 - 38.7, "accuracy gain"}\%.
```
- Every `\num{}` formula must evaluate correctly
- Use `\num{}` for any derived/computed values
