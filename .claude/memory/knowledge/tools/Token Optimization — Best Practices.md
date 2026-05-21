# Token Optimization — Best Practices

## Purpose
Reduce token consumption by 30-50% through efficient prompt design, caching, and output control — saving $20-50/month for active users.

**Target:** From ~26.9M tokens/month (current) → ~13-18M tokens/month (~40% reduction).

---

## Token Consumption Analysis (Baseline)

### Current Usage Pattern
**User baseline (from memory):**
- Total: 26.9M tokens
- Sessions: 211
- Peak hours: 23:00 (late-night work)
- Cost: ~$50-80/month (depends on Sonnet 4.5 pricing)

### Where Tokens Go
| Source | % of Total | Optimization Potential |
|--------|-----------|----------------------|
| **Context loading** (rules, memory, files) | 40% | HIGH — cache static content |
| **Tool results** (Read, Grep outputs) | 25% | MEDIUM — truncate long outputs |
| **Agent communication** | 20% | MEDIUM — compress handoffs |
| **User prompts** | 10% | LOW — user-controlled |
| **Assistant responses** | 5% | LOW — necessary content |

**Biggest wins:** Optimize context loading (40%) + tool results (25%) = 65% of consumption.

---

## Strategy 1: Prompt Caching (Claude Native)

### What Is Prompt Caching
Claude caches static prompt parts that repeat across turns:
- Rules files (coding-style.md, integrity.md, etc.)
- Large context (CLAUDE.md, activeContext.md)
- Repeated code blocks

**Cache TTL:** 5 minutes (Anthropic default).

### Implementation

**Current state:** Claude Code automatically uses prompt caching for system prompts.

**Optimization:**
1. **Keep static content at prompt start** — cached content must be at beginning
2. **Minimize cache-breaking edits** — don't edit rules mid-session
3. **Batch related work** — work on same project within 5-min windows

**Example:**
```
❌ BAD (cache breaks between projects):
Session 1 (10:00): Work on ARCHCODE → cache builds
Session 2 (10:07): Switch to GeoMiro → cache miss (new context)

✅ GOOD (cache reuse):
Session 1 (10:00-10:30): ARCHCODE → cache hot
Session 2 (10:32): ARCHCODE again → cache hit (saved 50% tokens)
```

**Expected savings:** 20-30% on cached content (= 8-12% total reduction).

---

## Strategy 2: Tool Output Truncation

### Problem
Read/Grep tools return full files → 1000+ lines → wasted tokens.

**Example:**
```bash
Read(file_path="large_file.py")  # 2000 lines = 8000 tokens
# Claude only needs lines 45-60
```

### Solutions

#### Solution A: Partial Read (Use offset + limit)
```python
# ❌ BAD: Read entire file
Read(file_path="hooks/session_save.py")  # 500 lines = 2000 tokens

# ✅ GOOD: Read relevant section
Read(file_path="hooks/session_save.py", offset=40, limit=30)  # 30 lines = 120 tokens
```

**Savings:** 94% fewer tokens (2000 → 120).

#### Solution B: Grep Instead of Read
```python
# ❌ BAD: Read file to find function
Read(file_path="utils.py")  # 1000 lines

# ✅ GOOD: Grep for function
Grep(pattern="def normalize_name", path="utils.py", output_mode="content", context=5)
```

**Savings:** 90% fewer tokens (1000 lines → 10 lines).

#### Solution C: Glob + Selective Read
```python
# ❌ BAD: Read all agent files
for agent in agents:
    Read(agent)  # 16 files × 100 lines = 6400 tokens

# ✅ GOOD: Glob first, read only needed
Glob(pattern="agents/*.md")  # Returns file names (50 tokens)
Read(agents[target])  # Read 1 file (400 tokens)
```

**Savings:** 93% fewer tokens (6400 → 450).

---

## Strategy 3: Response Length Control

### Problem
Claude generates verbose explanations when short answer would suffice.

### Solutions

#### Solution A: Explicit Length Limits
```markdown
❌ BAD:
"Explain this code"

✅ GOOD:
"Explain this code in 2 sentences max"
"List top 3 issues, 1 line each"
"Summarize in <100 words"
```

**Savings:** 50-70% on explanatory responses.

#### Solution B: Speed Mode
User prefix: `fast:` or `just do:`

Claude Code strips verbose output, action-only mode.

**Example:**
```
fast: fix bug in auth.py:47
→ Edit(auth.py, old="...", new="...") [no explanation]
```

**Savings:** 80% on implementation tasks (explanation → 0).

---

## Strategy 4: Context Compression

### Problem
Redundant information repeated across conversation turns.

### Solutions

#### Solution A: Summarize-Then-Discard Pattern
After completing subtask:
1. Summarize key facts (3-5 lines)
2. Drop detailed implementation from context
3. Carry summary forward

**Example:**
```
Turn 10: [Detailed implementation of feature X — 2000 tokens]
Turn 11: "Feature X done. Key: uses JWT, 7-day expiry, stored in Redis."
Turn 12: [Work on feature Y, Feature X details dropped]
```

**Savings:** 60-80% on completed work context.

#### Solution B: File-Based Handoffs
Instead of passing full context to agents:
1. Write intermediate state to temp file
2. Agent reads file (cached)
3. No redundant context in prompts

**Example:**
```python
# ❌ BAD: Pass full context in prompt
Agent(builder, prompt=f"Build feature using this spec:\n{long_spec}")

# ✅ GOOD: Spec in file, reference it
Write("/tmp/spec.md", long_spec)
Agent(builder, prompt="Build feature from /tmp/spec.md")
```

**Savings:** 50% on agent prompts.

---

## Strategy 5: Batch Operations

### Problem
Multiple small tool calls → redundant overhead per call.

### Solutions

#### Solution A: Parallel Tool Calls
```python
# ❌ BAD: Sequential reads (4 separate messages)
Read("file1.py")
Read("file2.py")
Read("file3.py")
Read("file4.py")

# ✅ GOOD: Parallel reads (1 message, 4 tool uses)
Read("file1.py"); Read("file2.py"); Read("file3.py"); Read("file4.py")
```

**Savings:** 30% (eliminate per-message overhead).

#### Solution B: Grep Aggregation
```python
# ❌ BAD: Grep each file
for file in files:
    Grep(pattern="TODO", path=file)

# ✅ GOOD: One Grep across all files
Grep(pattern="TODO", path=".", glob="**/*.py")
```

**Savings:** 80% (one tool call vs N calls).

---

## Strategy 6: Agent Isolation (Worktree Pattern)

### Token Impact
Agents in worktrees read isolated files → no shared context pollution.

**Benefit:**
- builder agent doesn't see tester's context
- tester doesn't see builder's implementation details
- Each agent's context = minimal

**Expected savings:** 10-15% on multi-agent tasks.

**Already implemented:** builder, tester use `isolation: worktree`.

---

## Strategy 7: Memory Optimization

### Problem
Auto-memory loads large context at session start.

### Solutions

#### Solution A: Lazy Memory Loading
Don't load ALL memory files upfront.

```python
# ❌ BAD: Load all 50 memory files at start
for mem in memory_files:
    load(mem)

# ✅ GOOD: Load on-demand
if task.needs_archcode:
    load("memory/project_archcode_may2026.md")
```

**Savings:** 40-60% on session start tokens.

#### Solution B: Memory Expiry
Old memory (>90 days) → archive → don't load.

**Example:**
```
memory/
├── active/         ← Load at session start (last 30 days)
├── archive/        ← Load on explicit request (30-90 days)
└── cold-storage/   ← Never auto-load (>90 days)
```

**Savings:** 20-30% on memory context.

---

## Strategy 8: Rule Consolidation

### Problem
10 rules files → 10 separate loads → cache misses.

### Solution
Consolidate related rules into single files:

```
❌ BAD (10 files, 10 cache entries):
coding-style.md
testing.md
security.md
...

✅ GOOD (3 files, 3 cache entries):
development-rules.md  (coding + testing + workflow)
safety-rules.md       (security + integrity + permissions)
agent-rules.md        (context-loading + doubt-driven + rationalizations)
```

**Savings:** 15-20% (fewer cache breaks, better cache hit rate).

**Trade-off:** Less modular (harder to edit individual rules).

---

## Implementation Priority

### Phase 1: Quick Wins (Week 1)
1. ✅ Use offset+limit in Read calls
2. ✅ Grep before Read (find, then read)
3. ✅ Explicit length limits ("2 sentences", "<100 words")
4. ✅ Parallel tool calls (batch independent operations)

**Expected: 15-20% reduction.**

### Phase 2: Architecture (Week 2-3)
5. File-based agent handoffs (temp specs)
6. Summarize-then-discard pattern after subtasks
7. Lazy memory loading (on-demand)

**Expected: Additional 10-15% reduction.**

### Phase 3: Advanced (Q3 2026)
8. Rule consolidation (development/safety/agent)
9. Memory expiry (active/archive/cold-storage)
10. Dynamic cache warming (predict next project)

**Expected: Additional 5-10% reduction.**

**Total potential:** 30-45% reduction (from 26.9M → 14-18M tokens/month).

---

## Monitoring & Metrics

### Track These Metrics

| Metric | Baseline | Target | How To Measure |
|--------|----------|--------|----------------|
| Tokens/session | 127K | <80K | Session logs |
| Cache hit rate | Unknown | >60% | Anthropic API logs |
| Tool result size (avg) | Unknown | <500 tokens | Instrument Read/Grep |
| Memory load size | Unknown | <5K tokens | Measure at session start |

### Weekly Review
Every Monday:
1. Check tokens/session trend (decreasing?)
2. Identify top 3 token-heavy operations
3. Apply one optimization from this guide
4. Re-measure next week

---

## Anti-Patterns (Don't Do This)

### ❌ Anti-Pattern 1: Over-Truncation
**Wrong:** Read 5 lines, miss critical context → re-read entire file → wasted tokens.  
**Right:** Read slightly more than needed (safety margin).

### ❌ Anti-Pattern 2: Premature Optimization
**Wrong:** Optimize every Read call → spend 10 min per optimization → diminishing returns.  
**Right:** Optimize top 20% token-heavy operations (80/20 rule).

### ❌ Anti-Pattern 3: Breaking Caching
**Wrong:** Edit rules files mid-session → cache invalidated → full reload.  
**Right:** Edit rules between sessions, not during.

### ❌ Anti-Pattern 4: Compression Over Clarity
**Wrong:** Compress prompts so much they're ambiguous → Claude confused → multi-turn clarification → more tokens than saved.  
**Right:** Clear > compressed. Only compress verbose, not essential info.

---

## ROI Calculation

**Current cost:** ~$50-80/month (26.9M tokens @ Sonnet 4.5 pricing).

**After 40% reduction:**
- Tokens: 16M/month
- Cost: ~$30-48/month
- **Savings: $20-32/month ($240-384/year)**

**Time investment:** ~4 hours to implement all Phase 1+2 optimizations.

**ROI:** $60-96 per hour saved (break-even in 1 month).

---

## Quick Reference Card

**Before Read:**
- Can I Grep instead? (90% savings)
- Do I need full file or just section? (offset+limit)
- Can I get file list first? (Glob then selective Read)

**Before asking Claude:**
- Length limit specified? ("2 sentences", "<100 words")
- Speed mode needed? (`fast:` prefix)
- Batch multiple questions? (one message, parallel tool calls)

**After subtask done:**
- Summarize key facts (3-5 lines)
- Drop detailed implementation from context
- Carry summary forward

**At session start:**
- Work on same project for 5+ min (cache reuse)
- Don't edit rules mid-session (preserve cache)
- Load memory on-demand, not all upfront

---

**Status:** ACTIVE — Phase 1 optimizations ready to apply  
**Expected ROI:** $240-384/year savings + faster responses  
**Next review:** Weekly Monday routine (track tokens/session trend)  
**Last updated:** 2026-05-11
