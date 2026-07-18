# Stack Maturity Map — Wardley-style

_Evolution axis: Genesis → Custom → Product → Commodity_
_Read as: what to invest in (Genesis→Custom), what to stabilize (Custom→Product), what to stop touching (Commodity)._

**Last updated:** 2026-07-18 (hook count + `permission_policy.py` entry; rest of this file not re-audited this pass)

---

## Hooks (88 total)

### Commodity — stable, don't touch unless broken
| Hook | What it does |
|------|-------------|
| `pre_commit_guard.py` | Lint + reviewer reminder before commit |
| `session_start/end/save.py` | Lifecycle state |
| `post_commit_memory.py` | Persist activeContext after commit |
| `post_format.py` | Auto-format after Write/Edit |
| `utils.py` | Shared primitives |

### Product — mature, reusable, predictable
| Hook | What it does |
|------|-------------|
| `project_classifier.py` | Dispatcher: project type → methodology |
| `knowledge_librarian.py` | Pre-task context injection from memory |
| `pattern_extractor.py` | Extract [AVOID]/[REPEAT] after fix: commits |
| `evidence_guard.py` | Block claims without evidence markers |
| `skeptic_auto_trigger.py` | Auto-invoke skeptic on 5 trigger patterns |
| `validation_theater_guard.py` | Detect synthetic-data validation fraud |
| `doc_registry.py` | Content-addressed document dedup (SHA256) |
| `file_auto_parser.py` | Parse files mentioned in prompt; cache by SHA256 |
| `expert_registry.py` | Compiled Python experts with test_cases + rollback |
| `pre_compact.py / post_compact.py` | Compact lifecycle hooks |
| `read_before_edit.py` | Enforce Read before Edit |
| `rationalization_detector.py` | Flag known excuse patterns |
| `spot_check_guard.py` | Random 3-claim verification after 10+ facts |

### Custom — working but still evolving, invest here
| Hook | What it does | Next evolution |
|------|-------------|---------------|
| `claim_entropy_tracker.py` | Monotone invariant for claim.md | Add cross-file entropy accumulation |
| `null_results_pre_check.py` | Warn on duplicate experiment at prompt-time | Semantic matching (not just token overlap) |
| `promotion_gate_guard.py` | 5 Perelman conditions before PROMOTE | Add STPA unsafe-action check (Tier 1 todo) |
| `estimand_guard.py` | Enforce estimand before experiment | Add ICE strategy validation |
| `hypothesis_router.py` | Route hypotheses to FL tier | Integrate with null_results index |
| `drift_guard.py` | Detect claim scope drift | Link to specific claim_entropy delta |
| `goal_budget_guard.py` | Enforce turn budget on /goal | Add token-level budget tracking |
| `memory_guard.py` | Protect memory/ from accidental writes | Extend to agent-memory/ |
| `moc_autolink.py` | Obsidian MOC link injection | Add backlink validation |
| `doc_bridge.py` | Bridge between doc formats | Add Excel/PDF validation |
| `permission_policy.py` | Auto-allow/deny/ask Bash commands by pattern | Was mislabeled Commodity here until 2026-07-18 (SEC-03): registered under the wrong hook event (`PermissionRequest`, which never fires given this repo's `Bash(*)` allow rule), so it silently never ran. Fixed (moved to `PreToolUse`), and a CI guard (`tests/test_hook_reachability.py`) now catches this specific regression class. Keep here, not in Commodity, until it accumulates a track record post-fix. |

### Genesis — experimental, unstable, high-risk/high-reward
| Hook | What it does | Maturity blocker |
|------|-------------|-----------------|
| `cogniml_client.py` | CogniML integration | External API instability |
| `vector_store.py` | Semantic search over memory | No regression suite yet |
| `smart_model_router.py` | Route to model by task complexity | Cost model not calibrated |
| `team_rebalance.py` | Dynamic agent team composition | Coordination logic unproven |
| `ace_reflector.py` | Autonomous capability expansion | Scope undefined |
| `webhook_notify.py` | External webhook on events | No auth model yet |
| `elicitation_guard.py` | Guard against data elicitation attacks | Edge cases uncharted |
| **STPA-unsafe-action-checker** | _(not built yet)_ Check agents for unsafe control actions | Not implemented |

---

## Agents (13 custom)

### Product
`reviewer` · `builder` · `tester` · `navigator` · `explorer` · `sec-auditor` · `reviewer`

### Custom (invest in)
`skeptic` — needs context-asymmetry enforcement at invocation site  
`verifier` — needs integration with evidence_guard  
`architect` — needs Wardley-aware scope check  

### Genesis
`scope-guard` — logic works, triggering conditions too broad  
`skill-suggester` — useful but no feedback loop on suggestions  

---

## Rules (9 active)

### Commodity
`coding-style.md` · `security.md` · `testing.md` · `permissions.md`

### Product
`integrity.md` · `doubt-driven-development.md` · `skeptic-triggers.md` · `context-loading.md`

### Custom (invest in)
`falsification-ladder.md` — OSA integration mature; STPA-lite is the next extension  
`estimand-ops.md` — solid spec, needs hook-level enforcement (partially in estimand_guard)  
`perelman-audit.md` — recent (2026-06-20), not yet battle-tested  
`audit-verification-gate.md` — proven but Glob Path Trap rule is new  

---

## Strategic Reads

**Invest now (Genesis → Custom):**
- STPA unsafe-action checker for agents
- vector_store semantic matching for null_results_pre_check
- token-level budget tracking in goal_budget_guard

**Stabilize (Custom → Product):**
- `claim_entropy_tracker` — add integration tests for edge cases
- `null_results_pre_check` + `promotion_gate_guard` — run on 5 real experiments

**Stop touching (Commodity is fine):**
- `pre_commit_guard` — works, don't add features
- `session_*` — if it ain't broke

**Watch, don't yet call stable:**
- `permission_policy` — was labeled "stop touching" here for a month while silently non-functional (wrong hook event, SEC-03). "Commodity" in this map means "stop auditing it," which is exactly how that went undetected. Needs a real track record post-fix before returning to Commodity.

**Kill if no usage in 60 days:**
- `cogniml_client.py` — external dependency, no active use
- `ace_reflector.py` — undefined scope
- `webhook_notify.py` — no consumers

---

## Evolution Heuristics

```
Genesis → Custom:  needs regression suite + 3 real-world uses
Custom → Product:  needs 10+ uses + documented edge cases + no surprise failures
Product → Commodity: stable API, zero active development, treat as infrastructure
```

_Update this file when a hook ships new tests or fails in production._
