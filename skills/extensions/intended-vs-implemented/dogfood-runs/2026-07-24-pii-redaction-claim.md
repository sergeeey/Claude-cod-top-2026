# Dogfood run — intended-vs-implemented vs README's PII-redaction claim

**Purpose:** real promotion evidence for `maturity: dogfooded` (P2 plan item 16,
`docs/baselines/2026-07-24-plan.md`), per `docs/skill-maturity-criteria.md`.

**Method:** a fresh `explorer`-type agent was given only the path to
`skills/extensions/intended-vs-implemented/SKILL.md` and instructed to follow
its 5-step protocol against a specific real claim in this repo's own
`README.md` (lines 451-452, before this run's fix): "PII Redaction — 12
patterns" listing 10 named categories, claimed to run "before external MCP
calls." This is a real, previously-existing, unverified claim -- not a
constructed test case -- so this run needed independent tool verification,
not a pre-known answer key.

**Verification (`rules/audit-verification-gate.md`):** all citations
independently re-checked:
- `scripts/redact.py:20-45` `PATTERNS` list -- counted personally: exactly 12
  `(regex, replacement)` tuples, confirming the numeric claim. Confirmed the
  2 categories missing from the README's 10-item list (Slack token `xoxb-`
  at line 30, generic secret/token/password assignment at lines 35-38).
- `hooks/hooks.json`: `PreToolUse` block starts at line 63, `scripts/redact.py`
  is wired at lines 147-151 inside the `"matcher": "mcp__*"` sub-block that
  starts at line 130 -- confirming the agent's specific wiring claim exactly
  (event type, matcher, and line numbers all independently reproduced).

**Result:** claim overall MATCHES with one real LOW-severity documentation
gap (2 of 12 real patterns weren't named in the README's illustrative list).
Fixed directly in this same change (`README.md:451-452`) since it was a
1-line, unambiguous, low-risk correction the audit itself proposed as the
FIX. The PreToolUse/`mcp__*` wiring claim ("before external MCP calls") was
exactly correct, no gap.

---

## Verbatim agent output

MATCH

FINDING 1
- Severity: LOW
- Type: documentation-accuracy (pattern-count vs. named-category count)
- CLAIMED: README.md:451-452 -- "PII Redaction -- 12 patterns" stripped, listing 10 named categories (National IDs · Bank cards · IBAN · API keys · GitHub tokens · AWS keys · JWT · Email · Phone · IPs).
- IMPLEMENTED: `scripts/redact.py:20-45` `PATTERNS` list contains exactly 12 `(regex, replacement)` tuples [VERIFIED-read]: National ID (line 22), Card (24), IBAN (26), API key `sk-` (28), GitHub token `ghp_` (29), Slack token `xoxb-` (30, **not named in README**), AWS key `AKIA` (31), JWT (33), generic secret/token/password assignment (35-38, **not named in README**), IP (40), Email (42), Phone (44).
- GAP: The "12 patterns" numeric claim is accurate [VERIFIED-read] (counted 12 tuples), but the README's category list names only 10 of the 12 -- it omits Slack tokens (`xoxb-`) and the generic `token/password/secret=...` assignment pattern.
- FIX: Either update README's category list to include "Slack tokens" and "Generic secret assignments" (10->12 names matching the count), or clarify the list is illustrative/non-exhaustive. **Applied: updated the category list (this commit).**

FINDING 2 (informational, not a gap -- confirms claim)
- Severity: N/A (confirmation)
- Type: trust-boundary wiring check
- CLAIMED: README.md:451 -- redaction happens "before external MCP calls."
- IMPLEMENTED: `hooks/hooks.json:63` registers this under the `"PreToolUse"` event [VERIFIED-grep], and `scripts/redact.py` is wired at lines 147-151 under `"matcher": "mcp__*"` [VERIFIED-read] -- i.e., PreToolUse hook scoped specifically to tools matching the `mcp__*` prefix (MCP tool calls), not globally to all tool calls.
- GAP: none. The wiring matches the specific claim exactly.

Overall: all 10 named README categories are present as working regex patterns [VERIFIED-read]; the "12 patterns" count is numerically correct [VERIFIED-read]; the PreToolUse/`mcp__*` wiring claim is exactly correct [VERIFIED-grep]. Only imprecision found is Finding 1 (LOW), now fixed.
