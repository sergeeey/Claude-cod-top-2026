# Troubleshooting — Solving Common Problems

## Diagnostic Checklist (10 Points)

Check from simple to complex — 90% of problems are resolved in the first 5 points.

- [ ] **1. `/doctor`** — is Claude Code healthy? No authentication errors?
- [ ] **2. `/context`** — is the context not overflowing? If > 60% → `/compact`
- [ ] **3. `/usage`** — are subscription limits not exceeded?
- [ ] **4. `/permissions`** — are permissions configured? Is the tool not blocked?
- [ ] **5. Is the prompt specific?** — not "fix tests", but "fix auth.spec.ts:45, mock returns undefined"
- [ ] **6. Are files referenced explicitly?** — `@path/to/file` instead of describing in words
- [ ] **7. Is the error copied exactly?** — full stack trace, not a paraphrase
- [ ] **8. `/clear` + repeat request** — fresh context solves half of problems
- [ ] **9. Different model** — `/model sonnet` for routine tasks, opus for complex ones
- [ ] **10. Subagent** — isolate the task via the Agent tool

---

## 1. Claude Ignores Instructions from CLAUDE.md

**Symptom**: Claude doesn't follow Evidence Policy, doesn't mark facts,
ignores Plan-First or 80/20 rules.

**Cause**:
- CLAUDE.md is too long (> 100 lines) — instructions get "buried"
- Context is filled to 70%+ — early instructions are pushed out of the attention window
- Instructions written as prose (paragraphs) instead of structured rules (bullet points)

**Solution**:
1. Check `/context` — if > 60%, run `/compact`
2. Check CLAUDE.md size: `wc -l ~/.claude/CLAUDE.md` (recommendation: ≤ 80 lines)
3. Move detailed rules to `rules/` for lazy loading
4. Rewrite prose as bullet-point constraints ("ALWAYS X", "NEVER Y")

**How to Prevent**:
- `/clear` between unrelated tasks (not `/compact`, but `/clear`)
- Modular architecture: CLAUDE.md (core) + rules/ (by context) + skills/ (by trigger)
- Evidence Policy in the top third of CLAUDE.md — not at the end of the file

---

## 2. Claude Invents Non-Existent APIs/Methods

**Symptom**: Claude tries a method → error → tries another invented method →
gets stuck in a loop with 5+ attempts using non-existent APIs.

**Cause**:
- Claude did not explore the codebase before writing code
- Plan-First workflow not activated (Explore → Design → Plan → Code)
- Stuck Detection did not fire (or is not configured)

**Solution**:
1. Interrupt (Esc)
2. Give an explicit instruction:
   ```
   Read the actual source file first.
   List all available methods.
   Then write code using ONLY existing methods.
   ```
3. Use explorer subagent to explore the codebase
4. If it repeats — check that CLAUDE.md contains Stuck Detection

**How to Prevent**:
- Evidence Policy: marker `[VERIFIED]` requires Claude to verify a fact with a tool
- Plan-First: 3+ files = a mandatory plan with exploration
- Stuck Detection: 3 failed attempts → STOP → report → alternative

---

## 3. MCP Server Not Connecting

**Symptom**: error when calling an MCP tool, "server not found", timeout,
or Claude doesn't see MCP tools.

**Cause**:
- Server is not running or the process crashed
- API keys expired or not configured
- Profile not switched (needed server is in science.json but core.json is active)
- Configuration in .mcp.json (Cursor format) instead of settings.local.json (Claude Code format)

**Solution**:
1. Check status: `/mcp` or `claude mcp list`
2. Check current profile: `cat ~/.claude/settings.local.json | head -5`
3. Reconnect: `claude mcp remove <name>` → `claude mcp add -s user <name> -- <command>`
4. Check env vars: `echo $ANTHROPIC_API_KEY` (or the relevant key)
5. Switch profile: `powershell ~/.claude/mcp-profiles/switch-profile.ps1 science`

**How to Prevent**:
- MCP profiles instead of connecting all servers simultaneously
- `claude mcp list` at session start (hook `session_start.py` will remind)
- Configuration via `claude mcp add`, NOT via .mcp.json

**Important**: after switching profiles — restart Claude Code!

---

## 4. Hooks Not Firing

**Symptom**: post_format doesn't format files, pre_commit_guard doesn't block
dangerous commands, memory_guard doesn't remind to update memory.

**Cause**:
- Path to script is incorrect (relative instead of absolute)
- Script does not have execution permissions (Linux/Mac: `chmod +x`)
- Matcher doesn't match the tool name (case-sensitive: `Bash`, not `bash`)
- Python not found in PATH
- Timeout is too small

**Solution**:
1. Check `/hooks` — list of registered hooks
2. Check path: `ls -la ~/.claude/hooks/post_format.py`
3. Check matcher: in settings.json `"Bash"` (capital B), `"Edit|Write"` (capitalized)
4. Manual test: `echo '{"tool": "Bash"}' | python ~/.claude/hooks/pre_commit_guard.py`
5. Check timeout: increase to 15-30 seconds if the script is complex

**How to Prevent**:
- Absolute paths in settings.json: `python /c/Users/user/.claude/hooks/script.py`
- After creating a hook — test from terminal with test JSON on stdin
- Matcher = exact tool name with correct capitalization

---

## 5. Evidence Markers Not Appearing in Responses

**Symptom**: Claude answers without `[VERIFIED]`, `[INFERRED]`, `[UNKNOWN]` markers.
Facts are presented as absolute truths without indicating confidence level.

**Cause**:
- Evidence Policy got "buried" in a long CLAUDE.md (too far down in the file)
- Context is filled > 70% and early instructions are displaced
- Model at medium effort skips "optional" marking
- Task is simple and Claude decides marking is excessive

**Solution**:
1. Verify Evidence Policy is in CLAUDE.md (lines 58-66) — in the top half
2. If context > 60% → `/compact`
3. For critical questions: `ultrathink` or explicitly request marking
4. Explicit prompt: "mark every fact with its evidence level"

**How to Prevent**:
- Evidence Policy in the top third of CLAUDE.md (not at the end)
- `rules/integrity.md` contains the extended version for auto-loading
- Good habit: when Claude makes a questionable claim — ask "is this [VERIFIED] or [INFERRED]?"

---

## 6. Redaction Hook Blocking Legitimate Data

**Symptom**: redact.py replaces with `[REDACTED]` legitimate data — project IDs,
coordinates, metrics that look like PII.

**Cause**:
- Regex pattern is too broad
- A new type of ID in the project matches a PII pattern
- Exceptions don't cover the specifics of the current project

**Solution**:
1. Check what exactly was blocked in the hook's stderr
2. Add an exception to the EXCEPTIONS list in `scripts/redact.py`
3. Run tests: `python scripts/test_redact.py`
4. Temporary: remove the redact matcher from settings.json (don't forget to restore!)

**How to Prevent**:
- When adding patterns to redact.py — test for false positives
- Exceptions for domain-specific IDs (ClinVar VCV, dbSNP rs, genomic chr17:...)
- Regular runs of test_redact.py with data from current projects

---

## 7. Claude Responds Slowly (30+ Seconds)

**Symptom**: every message takes 30+ seconds to process, noticeable delay
before tool selection.

**Cause**:
- Too many MCP servers (each adds latency during tool routing)
- Context is overflowing (> 80%)
- Rate limit on subscription
- Complex hooks with large timeouts block the response

**Solution**:
1. `claude mcp list` — how many servers are connected?
2. Switch to CORE profile: `switch-profile.ps1 core`
3. `/compact` or `/clear` to free up context
4. `/usage` — check rate limits
5. Check hook timeouts in settings.json (no more than 15 seconds)

**How to Prevent**:
- MCP profiles: 5 servers in core instead of 16
- `/clear` between tasks
- Hooks: 10-15 second timeout maximum

---

## 8. After /compact Claude Lost Context

**Symptom**: after compaction Claude doesn't remember decisions made, re-asks
already discussed questions, suggests rejected options.

**Cause**:
- Compaction compresses history, losing details from early messages
- Decisions were stored only in chat, not in memory files
- PreCompact hook is not configured or did not fire

**Solution**:
1. `/compact focus on [topic]` — specify what to preserve during compaction
2. Check per-project memory: `cat .claude/memory/activeContext.md`
3. Critical decisions must be in memory files, not just in history
4. If lost — restore from git: `git log --oneline -10`

**How to Prevent**:
- `hooks/pre_compact.py` — auto-save context before compaction
- Important decisions → `decisions.md` (architectural) or `activeContext.md` (current)
- Good habit: after a key decision — "save this to activeContext"
- `/compact` at 50% fill (don't wait for automatic at 80%+)
