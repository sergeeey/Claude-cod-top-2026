---
name: agent-governance
source: "github/awesome-copilot (adapted)"
version: "1.0"
description: >
  Governance, safety, and trust controls for AI agent systems: policy enforcement, intent classification, audit trails, trust scoring. Triggers: /agent-governance, agent safety, tool access control.
triggers: [agent-governance, agent safety, tool policy, access control, intent classification, audit trail, trust scoring, agent guardrails, безопасность агентов, политики агента, контроль доступа]
tokens: ~1800
---

<!-- BSV
Скил   : agent-governance
TL;DR  : Добавляет governance-слой к AI-агентам: политики, intent-классификация, аудит, trust-скоры
Вызов  : /agent-governance, agent safety, tool access control
НЕ для : output guardrails (это pre-execution safety), UI/UX-паттерны, LLM fine-tuning
-->

# Agent Governance Patterns

Patterns and techniques for adding governance, safety, and trust controls to AI agent systems. Works with any agent framework: PydanticAI, CrewAI, OpenAI Agents SDK, LangChain, AutoGen.

## Core Design Principle

> Intent classification happens **before** tool execution — a pre-flight safety check. This is fundamentally different from output guardrails which only check **after** generation.

---

## When to Use This Skill

- Building agents that call external tools (APIs, databases, file systems)
- Implementing policy-based access controls for agent tool usage
- Detecting dangerous or adversarial prompts before execution
- Creating trust scoring for multi-agent pipelines
- Building compliance-grade audit trails
- Enforcing rate limits, content filters, or tool restrictions

---

## Pattern 1 — Governance Policy (Declarative)

Define allowed/blocked tools and content filters in YAML or as a Python dataclass:

```yaml
# governance_policy.yaml
governance:
  level: standard          # open | standard | strict | locked
  allowed_tools:
    - web_search
    - read_file
    - write_file
  blocked_tools:
    - execute_shell
    - delete_database
  content_filters:
    - prompt_injection
    - pii_extraction
    - jailbreak_attempt
  rate_limits:
    calls_per_minute: 60
    max_concurrent: 5
```

```python
from dataclasses import dataclass, field
from enum import Enum

class GovernanceLevel(Enum):
    OPEN = "open"        # No restrictions
    STANDARD = "standard"  # Default — blocks high-risk tools
    STRICT = "strict"    # Allowlist only
    LOCKED = "locked"    # Read-only tools only

@dataclass
class GovernancePolicy:
    level: GovernanceLevel = GovernanceLevel.STANDARD
    allowed_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    content_filters: list[str] = field(default_factory=list)
    max_calls_per_minute: int = 60

    def allows_tool(self, tool_name: str) -> bool:
        if tool_name in self.blocked_tools:
            return False
        if self.level == GovernanceLevel.STRICT:
            return tool_name in self.allowed_tools
        return True
```

---

## Pattern 2 — Semantic Intent Classification

Classify user intent **before** routing to tools. Catch dangerous requests early:

```python
from enum import Enum
import re

class IntentCategory(Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"

# Fast heuristic classifier (no LLM call needed for common cases)
DANGEROUS_PATTERNS = [
    r"ignore (previous|all|above) instructions",
    r"you are now",
    r"pretend (you are|to be)",
    r"forget (your|all) (rules|guidelines|training)",
    r"(drop|delete|truncate) (table|database|all)",
    r"rm -rf",
    r"exfiltrate|exfil|send (all|my|the) (data|files|credentials)",
]

SUSPICIOUS_PATTERNS = [
    r"(bypass|override|ignore) (security|policy|restrictions)",
    r"show (me|all) (passwords|secrets|api.?keys)",
    r"list all (users|emails|pii)",
]

def classify_intent(prompt: str) -> tuple[IntentCategory, str]:
    """Returns (category, reason). Fast path — no LLM required."""
    lower = prompt.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, lower):
            return IntentCategory.BLOCKED, f"Matched dangerous pattern: {pattern}"
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, lower):
            return IntentCategory.SUSPICIOUS, f"Matched suspicious pattern: {pattern}"
    return IntentCategory.SAFE, "No threat patterns detected"
```

For high-stakes decisions, escalate to an LLM classifier:

```python
async def classify_intent_llm(prompt: str, client) -> IntentCategory:
    """Secondary classifier for ambiguous cases — uses a small, fast model."""
    result = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        system="Classify intent as: SAFE, SUSPICIOUS, DANGEROUS, BLOCKED. Reply with one word only.",
        messages=[{"role": "user", "content": prompt}]
    )
    return IntentCategory(result.content[0].text.strip().lower())
```

---

## Pattern 3 — Tool-Level Governance Decorator

Wrap any tool function with policy enforcement:

```python
import functools
import time
from typing import Callable

def governed_tool(policy: GovernancePolicy):
    """Decorator: enforce policy before tool execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tool_name = func.__name__

            # 1. Policy check
            if not policy.allows_tool(tool_name):
                raise PermissionError(
                    f"Tool '{tool_name}' is blocked by governance policy "
                    f"(level={policy.level.value})"
                )

            # 2. Rate limit check
            # (integrate with your rate limiter of choice)

            # 3. Execute + audit
            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                audit_log(tool_name, args, kwargs, "success", time.monotonic() - start)
                return result
            except Exception as e:
                audit_log(tool_name, args, kwargs, f"error: {e}", time.monotonic() - start)
                raise

        return wrapper
    return decorator


# Usage:
policy = GovernancePolicy(level=GovernanceLevel.STRICT, allowed_tools=["read_file", "web_search"])

@governed_tool(policy)
async def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()
```

---

## Pattern 4 — Trust Scoring (Multi-Agent)

Track and decay trust scores for agents in a pipeline:

```python
import time
from dataclasses import dataclass, field

@dataclass
class AgentTrustScore:
    agent_id: str
    base_score: float = 1.0          # 0.0 – 1.0
    decay_rate: float = 0.01         # per call
    violation_penalty: float = 0.2
    _current_score: float = field(init=False)
    _call_count: int = field(default=0, init=False)

    def __post_init__(self):
        self._current_score = self.base_score

    @property
    def score(self) -> float:
        # Temporal decay: trust decreases slightly with each call
        return max(0.0, self._current_score - self.decay_rate * self._call_count)

    def record_violation(self, severity: float = 1.0) -> None:
        self._current_score -= self.violation_penalty * severity

    def record_call(self) -> None:
        self._call_count += 1

    def is_trusted(self, threshold: float = 0.5) -> bool:
        return self.score >= threshold


# In your orchestrator:
trust_registry: dict[str, AgentTrustScore] = {}

def get_or_create_trust(agent_id: str) -> AgentTrustScore:
    if agent_id not in trust_registry:
        trust_registry[agent_id] = AgentTrustScore(agent_id=agent_id)
    return trust_registry[agent_id]
```

---

## Pattern 5 — Audit Trail (Append-Only)

Compliance-grade logging for all agent actions:

```python
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

AUDIT_LOG_PATH = Path("audit/agent_actions.jsonl")

def audit_log(
    tool_name: str,
    args: tuple,
    kwargs: dict,
    outcome: str,
    duration_s: float,
    agent_id: str = "unknown",
) -> None:
    """Append-only JSONL audit entry. Never modifies existing records."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "tool": tool_name,
        "args_hash": hashlib.sha256(str(args).encode()).hexdigest()[:16],
        "kwargs_keys": list(kwargs.keys()),  # WHY: log structure, not values (PII safety)
        "outcome": outcome,
        "duration_ms": round(duration_s * 1000, 1),
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")
```

---

## Pattern 6 — Framework Integration Checklist

### PydanticAI
```python
from pydantic_ai import Agent
from pydantic_ai.tools import Tool

# Wrap each Tool with governed_tool decorator before registering
agent = Agent(model="claude-sonnet-4-5", tools=[governed_read_file, governed_web_search])
```

### OpenAI Agents SDK
```python
from agents import Agent, function_tool

@function_tool
@governed_tool(policy)
async def my_tool(param: str) -> str: ...
```

### CrewAI
```python
from crewai_tools import BaseTool

class GovernedTool(BaseTool):
    def _run(self, *args, **kwargs):
        category, reason = classify_intent(str(args))
        if category == IntentCategory.BLOCKED:
            return f"[BLOCKED] {reason}"
        return self._execute(*args, **kwargs)
```

---

## Governance Levels Quick Reference

| Level | Blocked | Allowed | Use Case |
|-------|---------|---------|----------|
| `open` | Nothing | Everything | Dev/local only |
| `standard` | High-risk tools (shell, DB delete) | Most tools | Production default |
| `strict` | Everything not in allowlist | Explicit allowlist | Financial/medical |
| `locked` | All write operations | Read-only tools | Audit/reporting agents |

---

## Integration Checklist

- [ ] GovernancePolicy defined and version-controlled
- [ ] `classify_intent()` called before any user-driven tool routing
- [ ] All tool functions wrapped with `@governed_tool`
- [ ] `audit_log()` writes to append-only JSONL
- [ ] Trust scores tracked per agent in multi-agent pipelines
- [ ] Governance level escalates automatically on repeated violations
- [ ] Audit log retention policy documented (GDPR: minimum 72h for breach evidence)
