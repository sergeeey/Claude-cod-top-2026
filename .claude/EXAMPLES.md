# Example Implementations — Living Documentation

> **Purpose:** Reference implementations showing how to extend Claude Code.  
> **Principle:** Copy → Modify → Test → Deploy.  
> **Status:** Always in sync with latest protocol (auto-updated with breaking changes).

---

## Quick Navigation

| Component | File | Use Case |
|-----------|------|----------|
| **Agent** | [agents/example-agent.md](agents/example-agent.md) | Create custom agents (builder, reviewer, analyzer) |
| **Hook** | [hooks/example-hook.py](hooks/example-hook.py) | Intercept events (validation, logging, routing) |
| **Skill** | Skills are markdown files in `~/.claude/skills/` | Add reusable capabilities |
| **Team** | [agents/teams/build-squad.md](agents/teams/build-squad.md) | Coordinate multiple agents |

---

## Why Examples-First Documentation?

**Traditional docs:** 10-page specification → outdated after 2 weeks → developers confused.

**Living examples:** Fully functional reference code → copy-paste → works immediately → always current.

**Benefits:**
- **Faster onboarding:** New developers copy example, modify 5 lines, done
- **Always accurate:** Example = runnable test, breaks if API changes
- **Self-documenting:** Code comments explain WHY, not just WHAT
- **Lower barrier:** Don't need to read full spec to contribute

**Pattern source:** [Claude Plugins Official](https://github.com/anthropics/claude-plugins-official) (Anthropic)

---

## Example 1: Creating a Custom Agent

### Use Case
You need an agent that analyzes code complexity and suggests refactoring.

### Steps

1. **Copy template:**
   ```bash
   cp agents/example-agent.md agents/complexity-analyzer.md
   ```

2. **Modify frontmatter:**
   ```yaml
   name: complexity-analyzer
   description: Analyzes code complexity and suggests refactoring opportunities
   tools: Read, Grep, Bash
   model: sonnet
   ```

3. **Update agent body:**
   ```markdown
   ## Process
   1. Read target files
   2. Run complexity analysis (cyclomatic, cognitive)
   3. Identify hotspots (complexity >15)
   4. Suggest refactoring (extract method, simplify conditionals)
   5. Return: report + prioritized recommendations
   ```

4. **Test:**
   ```markdown
   Agent(complexity-analyzer, description="Analyze auth.py", prompt="Find complexity hotspots in auth.py")
   ```

5. **Iterate:** Fix bugs, refine process, deploy.

**Time:** 15-30 minutes from copy to working agent.

---

## Example 2: Creating a Validation Hook

### Use Case
Block prompts containing API keys before they reach Claude (prevent secrets leakage).

### Steps

1. **Copy template:**
   ```bash
   cp hooks/example-hook.py hooks/secrets-guard.py
   ```

2. **Modify validation logic:**
   ```python
   def validate_prompt(prompt: str) -> Optional[str]:
       """Block prompts containing API keys."""
       # Regex for common API key formats
       patterns = [
           r"sk-[a-zA-Z0-9]{48}",  # OpenAI keys
           r"xoxb-[0-9]{10,13}-[a-zA-Z0-9]{24}",  # Slack tokens
           r"ghp_[a-zA-Z0-9]{36}",  # GitHub tokens
       ]
       
       for pattern in patterns:
           if re.search(pattern, prompt):
               return "Blocked: API key detected in prompt"
       
       return None
   ```

3. **Register in settings.json:**
   ```json
   {
     "hooks": {
       "UserPromptSubmit": {
         "script": "secrets-guard.py",
         "python": "/path/to/python"
       }
     }
   }
   ```

4. **Test:**
   ```bash
   echo '{"event": "UserPromptSubmit", "data": {"prompt": "My key is sk-abc123..."}}' | python hooks/secrets-guard.py
   # Should block
   ```

5. **Deploy:** Restart Claude Code, hook active.

**Time:** 10 minutes from copy to working hook.

---

## Example 3: Creating an Agent Team

### Use Case
Implement feature + tests in parallel (2x faster than sequential).

### Steps

1. **Copy template:**
   ```bash
   cp agents/teams/build-squad.md agents/teams/my-squad.md
   ```

2. **Define members:**
   ```yaml
   name: my-squad
   lead: architect
   teammates:
     - builder
     - tester
   strategy: parallel-worktree
   ```

3. **Define coordination:**
   ```markdown
   ## Coordination Protocol
   1. Architect creates spec
   2. Builder + tester receive spec simultaneously
   3. Builder implements in worktree-builder branch
   4. Tester writes tests in worktree-tester branch
   5. Lead merges both branches → run integration tests
   ```

4. **Invoke:**
   ```markdown
   Agent(my-squad, description="Feature X + tests", prompt="Implement feature X from spec.md")
   ```

**Time:** 20 minutes from copy to working team.

---

## Example 4: Skill Propagation (DRY Skills)

### Use Case
Multiple agents need same skill (e.g., `security-audit`). Keep it DRY.

### Steps

1. **Define skill once:**
   ```bash
   # Already exists: ~/.claude/skills/security-audit/SKILL.md
   ```

2. **Agents declare dependency:**
   ```yaml
   # agents/sec-auditor.md
   skills: [security-audit]
   
   # agents/security-guard.md
   skills: [security-audit]
   ```

3. **Sync skills to agents:**
   ```bash
   python scripts/sync-agent-skills.py
   # Copies skill to agents/sec-auditor/bundled-skills/
   #                  agents/security-guard/bundled-skills/
   ```

4. **Detect drift:**
   ```bash
   python scripts/sync-agent-skills.py --check
   # 0 errors → in sync
   # Drift detected → run without --check to fix
   ```

**Benefits:**
- Edit skill once → all agents updated
- No copy-paste errors
- Version consistency enforced

---

## Testing Your Implementation

### Agent Testing
```bash
# Smoke test (does it run without errors?)
Agent(your-agent, description="Smoke test", prompt="Say hello")

# Functional test (does it produce correct output?)
Agent(your-agent, description="Real task", prompt="Analyze auth.py")

# Edge case test (does it handle errors gracefully?)
Agent(your-agent, description="Missing file", prompt="Analyze nonexistent.py")
```

### Hook Testing
```bash
# Unit test (validate function works)
python -m pytest hooks/test_your_hook.py

# Integration test (hook receives correct JSON)
echo '{"event": "EventName", "data": {...}}' | python hooks/your-hook.py

# Validation test (settings.json valid)
python scripts/validate-hooks.py

# Live test (register + use Claude Code)
# Add to settings.json → restart Claude Code → test
```

### Team Testing
```bash
# Test coordination (members receive correct context)
Agent(your-team, description="Test", prompt="Simple task")

# Test parallelism (members work simultaneously)
# Check: multiple worktrees created, both active

# Test handoff (lead merges branches correctly)
# Check: both branches merged, no conflicts
```

---

## Best Practices

### For Agents
1. ✅ Always read `activeContext.md` first (project awareness)
2. ✅ Define Context Boundary (what agent receives/returns)
3. ✅ Use `isolation: worktree` if agent writes code
4. ✅ Keep `maxTurns` reasonable (10-15 for most tasks)
5. ✅ Document constraints (what NOT to do)
6. ❌ Don't give too many tools (security + clarity)
7. ❌ Don't make agents too generic (focused > versatile)

### For Hooks
1. ✅ Keep fast (<100ms) — hooks block event processing
2. ✅ Never block on error — pass through if hook crashes
3. ✅ Log everything (JSONL format)
4. ✅ Validate early (PreToolUse > PostToolUse)
5. ✅ Return clear error messages
6. ❌ Don't call external APIs (use agents instead)
7. ❌ Don't do heavy computation (use agents instead)

### For Skills
1. ✅ One skill = one capability (single responsibility)
2. ✅ Declare skills in agent frontmatter (auto-sync)
3. ✅ Version skills (breaking changes → new version)
4. ✅ Test skills independently before bundling
5. ❌ Don't duplicate skills across agents (use sync)

---

## Troubleshooting

### Agent Not Working

**Symptom:** Agent invocation fails or produces wrong output.

**Checklist:**
- [ ] Frontmatter valid? (name, description, tools present)
- [ ] Tools list minimal? (only necessary tools)
- [ ] Context Boundary defined? (receives/returns clear)
- [ ] Process steps numbered? (agent knows what to do)
- [ ] Tested with simple task first? (smoke test before complex)

### Hook Not Triggering

**Symptom:** Hook never runs, no logs generated.

**Checklist:**
- [ ] Registered in settings.json? (correct event name)
- [ ] Python path valid? (interpreter exists)
- [ ] Script executable? (`chmod +x hooks/your-hook.py`)
- [ ] JSON stdin/stdout? (test with echo | python)
- [ ] Claude Code restarted? (config changes need restart)

### Skill Not Syncing

**Symptom:** `sync-agent-skills.py` reports missing skill.

**Checklist:**
- [ ] Skill exists in `~/.claude/skills/`? (file present)
- [ ] Agent declares skill in frontmatter? (`skills: [name]`)
- [ ] Skill name matches file? (exact match, case-sensitive)
- [ ] Run sync without --check? (--check only detects, doesn't fix)

---

## Migration Guide (Protocol Changes)

When Claude Code protocol changes (e.g., v2.3 → v2.4):

1. **Update example files first:**
   - `agents/example-agent.md`
   - `hooks/example-hook.py`
   - This file (EXAMPLES.md)

2. **Test examples:**
   - Run smoke tests
   - Ensure examples work with new protocol

3. **Update production agents/hooks:**
   - Copy changes from examples
   - Test each production component
   - Deploy incrementally (not all at once)

4. **Document breaking changes:**
   - Add to CHANGELOG.md
   - Note in example comments
   - Update EXAMPLES.md

**Protocol versions:**
- v2.3 (current): Agent frontmatter with `skills`, `memory`, `isolation`
- v2.2 (legacy): Agent frontmatter without `isolation`
- v2.1 (legacy): Basic agent structure

---

## Contributing New Examples

Have a useful pattern? Add it as an example:

1. **Create example file:**
   - Clear comments explaining each part
   - Runnable without modifications
   - Include test instructions

2. **Add to this index:**
   - Update Quick Navigation table
   - Add Example N section
   - Include use case + steps

3. **Test thoroughly:**
   - Smoke test (runs without errors)
   - Functional test (produces correct output)
   - Edge case test (handles errors gracefully)

4. **Submit PR:**
   - Title: "Add example: [name]"
   - Description: Use case + benefits
   - Link to pattern source (if applicable)

---

## References

- **Pattern source:** [Claude Plugins Official](https://github.com/anthropics/claude-plugins-official) (example-plugin/)
- **Agents:** See `agents/*.md` for production examples
- **Hooks:** See `hooks/*.py` for production examples
- **Skills:** See `~/.claude/skills/` for available skills
- **Teams:** See `agents/teams/*.md` for coordination patterns
- **Scripts:** See `scripts/sync-agent-skills.py`, `scripts/validate-hooks.py`

---

**Status:** ACTIVE — examples always in sync with latest protocol  
**Protocol version:** v2.3  
**Last updated:** 2026-05-11  
**Next review:** When protocol changes (v2.4+)
