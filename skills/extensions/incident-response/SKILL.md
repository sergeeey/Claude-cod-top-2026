---
name: incident-response
source: "wshobson/agents (adapted)"
version: "1.0"
description: >
  Structured incident response: severity classification, runbook templates, escalation
  matrices, communication templates, and blameless postmortem writing. Triggers:
  /incident-response, postmortem, runbook, incident, outage, SEV1, инцидент, постмортем,
  авария на проде.
triggers: [incident-response, postmortem-writing, incident-runbook-templates, postmortem, runbook, incident, outage, SEV1, SEV2, on-call, инцидент, постмортем, авария на проде, разбор инцидента]
tokens: ~3800
---

<!-- BSV
Скил   : incident-response
TL;DR  : Runbook-шаблоны + бесстыдный постмортем для production-инцидентов
Вызов  : /incident-response, postmortem, runbook, SEV1, инцидент, авария на проде
НЕ для : планирования capacity, мониторинга в норме, code review без инцидента
-->

# Incident Response

Production-ready runbook templates and blameless postmortem framework.

---

## Part 1: Incident Runbook Templates

### Severity Classification

| Severity | Impact | Response SLA | Example |
|---|---|---|---|
| **SEV1** | Complete outage, data loss | 15 min | Production down, all users affected |
| **SEV2** | Major degradation | 30 min | Critical feature broken, >20% users |
| **SEV3** | Minor impact | 2 hours | Non-critical feature degraded |
| **SEV4** | Minimal impact | Next business day | Cosmetic, single user |

### Runbook Structure

```
1. Overview & Impact
2. Detection & Alerts
3. Initial Triage
4. Mitigation Steps
5. Root Cause Investigation
6. Resolution Procedures
7. Verification & Rollback
8. Communication Templates
9. Escalation Matrix
```

### Quick Checklist (for 3 AM brain)

```markdown
## Quick Checklist — [SERVICE NAME] Outage
- [ ] 1. Declare severity, open war room (#incidents channel)
- [ ] 2. Assign: Incident Commander, Communications Lead
- [ ] 3. Check service health dashboard (link)
- [ ] 4. Check recent deployments — was anything deployed in last 2h?
- [ ] 5. Roll back if deploy is suspect (Section 4.1)
- [ ] 6. Post initial notification to #status (template below)
- [ ] 7. Escalate if not mitigated within SLA
- [ ] 8. Update status every 15 min until resolved
```

### Service Runbook Template

```markdown
# [SERVICE NAME] Incident Runbook

## Runbook Metadata
| Field | Value |
|---|---|
| Last verified | YYYY-MM-DD |
| Owner | @team-name |
| Review cadence | After every SEV1/SEV2 |
| Dashboard | [link] |
| Logs | [link] |
| Alerts | [link] |

## 1. Overview
**Service:** [name]
**Dependencies:** [list upstream/downstream]
**Data criticality:** [PII / financial / non-sensitive]

## 2. Detection
Alert name: [AlertManager / PagerDuty rule name]
Typical symptom: [error rate >1%, latency P99 >2s, etc.]

## 3. Initial Triage (first 5 min)
```bash
# Check pod status
kubectl get pods -n [namespace]
# Prerequisites: kubectl configured, context = prod-cluster
# If fails: aws eks update-kubeconfig --name prod-cluster --region us-east-1

# Check recent events
kubectl describe deployment [name] -n [namespace] | tail -20

# Check logs (last 100 errors)
kubectl logs -l app=[name] -n [namespace] --since=10m | grep ERROR | tail -50
```

## 4. Mitigation Steps

### 4.1 — Recent bad deploy
```bash
# Check last 3 deploys
kubectl rollout history deployment/[name] -n [namespace]

# Roll back to previous
kubectl rollout undo deployment/[name] -n [namespace]

# Verify rollback
kubectl rollout status deployment/[name] -n [namespace]
```

### 4.2 — High memory / OOM
```bash
kubectl top pods -n [namespace]
# If OOM: patch resource limits temporarily
kubectl patch deployment [name] -n [namespace] \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"[name]","resources":{"limits":{"memory":"2Gi"}}}]}}}}'
```

### 4.3 — Database connection exhaustion
```sql
-- WARNING: Check count BEFORE terminating
-- DRY RUN:
SELECT count(*) FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '10 minutes';

-- EXECUTE only if count < 50:
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
WHERE state = 'idle' AND query_start < now() - interval '10 minutes';
```

## 5. Communication Templates

### Initial (within 5 min of declare)
```
[INVESTIGATING] SERVICE: [name] | SEV[N]
Impact: [what is broken, who affected, % traffic]
Started: [time UTC]
IC: @[name] | Comms: @[name]
Next update: 15 min
```

### Update (every 15 min)
```
[MITIGATING] SERVICE: [name] | SEV[N] | [duration]
Status: [Investigating / Mitigating / Monitoring]
Impact: [current impact]
Action: [what we are doing right now]
Next update: 15 min
```

### Resolution
```
[RESOLVED] SERVICE: [name] | SEV[N]
Duration: [X min]
Root cause: [one sentence]
Fix applied: [what was done]
Postmortem: [link — to be added]
```

## 6. Escalation Matrix
| Role | When to escalate | Contact |
|---|---|---|
| On-call engineer | Immediately | PagerDuty |
| Team lead | >15 min unresolved SEV1 | @[name] |
| VP Engineering | Customer data loss / >1h SEV1 | @[name] |
| Legal / Security | Data breach suspected | [email] |
```

### Troubleshooting Common Patterns

**Runbook steps work in staging but fail during real incident**
Add prerequisite check + fallback for every command:
```bash
# Step: restart deployment
# Prerequisites: kubectl configured, correct namespace
# If fails: check RBAC — run `kubectl auth can-i restart deployments -n [ns]`
kubectl rollout restart deployment/[name] -n [namespace]
```

**Engineer panics, skips steps out of order**
The Quick Checklist at top exists exactly for this. Mirror section numbers in checklist.

**Runbook outdated — cluster names, endpoints changed**
Add CI check that validates all `curl` URLs and `kubectl` context names weekly.

---

## Part 2: Blameless Postmortem

### When to Write a Postmortem

| Trigger | Required? |
|---|---|
| SEV1 or SEV2 | Yes |
| Customer-facing outage >15 min | Yes |
| Data loss or security incident | Yes |
| Novel failure mode | Yes |
| Near-miss with potential high severity | Yes |
| SEV3 with interesting root cause | Recommended |

### Blameless Culture

| Blame-focused | Blameless |
|---|---|
| "Who caused this?" | "What conditions allowed this?" |
| Punish individuals | Improve systems |
| Fear → hiding incidents | Safety → reporting everything |
| Individual blame | Systemic learning |

**Core principle:** If a human made an error that caused an incident, ask what made that error possible, not who made it.

### Postmortem Timeline

| Time | Action |
|---|---|
| T+0 | Incident declared |
| T+24h | Initial notes drafted (IC writes) |
| T+48h | Team review meeting (60 min) |
| T+72h | Action items assigned + tracked |
| T+7d | Postmortem published org-wide |
| T+30d | Action items progress reviewed |
| T+90d | Pattern analysis across postmortems |

### Comprehensive Postmortem Template

```markdown
# Postmortem: [Service] — [Date] — [Brief description]

**Severity:** SEV[N]
**Duration:** [start] to [end] UTC ([X] min total)
**Author(s):** [names]
**Status:** Draft / In Review / Final

---

## Executive Summary
[2-3 sentences: what broke, customer impact, root cause, how fixed]

## Impact
- **Users affected:** [N users / % of traffic]
- **Revenue impact:** [$N estimated]
- **SLA breach:** Yes / No (SLA = XX% uptime)
- **Data loss:** Yes / No

## Timeline (all times UTC)
| Time | Event |
|---|---|
| HH:MM | Alert fired: [alert name] |
| HH:MM | On-call engineer paged |
| HH:MM | [Observation / action] |
| HH:MM | Root cause identified |
| HH:MM | Mitigation applied |
| HH:MM | Incident resolved |
| HH:MM | Postmortem meeting |

## Root Cause Analysis — 5 Whys

**Symptom:** [observable failure]

1. **Why?** → [first cause]
2. **Why?** → [second cause]
3. **Why?** → [third cause]
4. **Why?** → [fourth cause]
5. **Why?** → [root cause — systemic, fixable]

**Root cause summary:** [One sentence]

## Contributing Factors
- [Factor 1: e.g., no runbook for this scenario]
- [Factor 2: e.g., alert threshold too high]
- [Factor 3: e.g., no circuit breaker on dependency]

## What Went Well
- [Thing 1: e.g., on-call paged in under 5 min]
- [Thing 2: e.g., rollback completed in 3 min]

## What Went Poorly
- [Thing 1: e.g., root cause took 45 min to identify]
- [Thing 2: e.g., status page not updated for 30 min]

## Action Items
| Action | Owner | Priority | Due | Status |
|---|---|---|---|---|
| [Add circuit breaker to X] | @engineer | P1 | YYYY-MM-DD | Open |
| [Update runbook with Y scenario] | @engineer | P2 | YYYY-MM-DD | Open |
| [Lower alert threshold from 5% to 1%] | @engineer | P2 | YYYY-MM-DD | Open |

## Lessons Learned
[What would prevent this class of incident?]
```

### Quick Postmortem Template (SEV3, minor incidents)

```markdown
# Quick Postmortem: [Service] — [Date]

**Duration:** [X min] | **Severity:** SEV3 | **Author:** [name]

**What happened:** [2 sentences]

**Root cause:** [1 sentence]

**Fix applied:** [1 sentence]

**Action items:**
- [ ] [Action] — @owner — [due date]
```

### 60-Minute Facilitation Agenda

| Time | Activity |
|---|---|
| 0-5 min | Ground rules: blameless, psychological safety |
| 5-20 min | Timeline walkthrough (IC narrates) |
| 20-35 min | 5 Whys root cause analysis |
| 35-50 min | Action items: owners, priorities, due dates |
| 50-60 min | "What went well" + lessons learned |

**Facilitator rules:**
- Redirect blame ("X made an error") to system ("X was in a position to make an error — why?")
- Ensure every attendee speaks at least once
- Action items must be specific, assigned, and time-bound — "investigate X" is not an action item

## Best Practices

1. Publish postmortems org-wide — learning should spread, not stay in the team
2. Track action item completion rate as a team metric (target: >80% on time)
3. Run quarterly pattern analysis: which categories of root cause repeat?
4. Game days / chaos engineering: test runbooks before they're needed at 3 AM
5. "Last Verified" date on every runbook — stale runbooks cause secondary incidents
