---
name: Wealth Protocol
description: Validation-first diagnostic workflow for specific knowledge, leverage stack, productization, and time-for-money leaks. Use for /wealth-protocol [excavate|audit|productize|escape|full|validate] when a user wants to turn expertise into testable leveraged assets without income guarantees.
when_to_use: Use when the user asks to find specific knowledge, audit Labor/Capital/Code/Media leverage, productize expertise, escape hourly work, convert skills into assets, or build a market-validation sprint.
argument-hint: "[excavate|audit|productize|escape|full|validate] [optional context]"
disable-model-invocation: false
allowed-tools: Read Grep Glob
---

# Wealth Protocol Skill

**Status:** v0.1.0 draft skill  
**Core rule:** this is not financial advice, not investment advice, and not a guarantee of income. Every niche, product, market, business model, revenue estimate, or 24-month projection is a `<hypothesis>` until validated with external market evidence.

## Purpose

Diagnose a user's specific knowledge, leverage stack, productization paths, and time-for-money leaks, then produce a validation-first roadmap toward scalable assets.

The skill is designed for:
- solo founders;
- consultants;
- developers;
- researchers;
- creators;
- knowledge workers;
- experts with messy, non-linear backgrounds.

It should convert vague personal expertise into:
1. a specific knowledge map;
2. leverage opportunities;
3. productized asset hypotheses;
4. equity-building conversions;
5. a 7-14 day validation sprint.

## When to Use

Use this skill when the user asks for:
- "find my niche";
- "audit my leverage";
- "productize my expertise";
- "turn my consulting into scalable assets";
- "escape hourly work";
- "build a business from my knowledge";
- "use Naval Ravikant leverage ideas";
- "create a monetization plan";
- "validate which product idea to pursue."

## When Not to Use

Do not use this skill for:
- investment advice;
- tax, legal, medical, or regulated financial advice;
- guarantees of income;
- get-rich-quick requests;
- requests to fabricate market data;
- requests to manipulate customers;
- requests to bypass compliance or platform rules.

For high-stakes finance, legal, tax, medical, or investment topics, provide general educational framing and recommend qualified human review.

## Modes

The mode is selected from the first argument.

If no mode is supplied, use `full`.

Supported modes:
- `excavate` — find specific knowledge and rare niche intersections.
- `audit` — audit Labor / Capital / Code / Media leverage.
- `productize` — turn expertise into a productized asset.
- `escape` — detect time-for-money leaks and convert them into equity-building assets.
- `full` — run the complete pipeline.
- `validate` — stress-test existing niche/product/business hypotheses.

## Required Inputs

Minimum useful input:

```yaml
interests_unpaid: []
career_path: ""
underrated_skills: []
income_streams:
  - activity: ""
    payment_model: ""
    hours_per_week: 0
    revenue_share_percent: 0
current_monthly_income: null
target_monthly_income: null
platforms_or_audience: []
assets: []
time_available_per_week: null
constraints: []
things_user_refuses_to_do: []
```

If fewer than 4 of these input areas are present, do not invent a strategy. Return `needs_more_data` and ask for the smallest missing input set, max 5 questions.

## Evidence Tags

Always separate evidence levels:

- `<fact>` — information explicitly provided by user or verified in files/tools.
- `<inference>` — logical conclusion from provided facts.
- `<hypothesis>` — unverified business, market, product, niche, or revenue claim.
- `<unknown>` — missing or uncertain information.
- `<risk>` — possible failure mode.
- `<metric>` — measurable criterion.
- `<gate>` — pass/fail decision point.
- `<action>` — concrete next step.

Never present a `<hypothesis>` as a `<fact>`.

## Operating Workflow

```text
Input
→ Environment Passport
→ Specific Knowledge Map
→ Leverage Audit
→ Productization Options
→ Time-for-Money Conversion
→ Market Validation Plan
→ 14-Day Sprint
→ Evidence Log
```

### 1. Environment Passport

Before strategy, classify:

```yaml
user_type:
  one_of: [developer, consultant, researcher, creator, operator, expert, mixed]
stage:
  one_of: [exploration, validation, first_revenue, scaling, pivot]
audience_status:
  one_of: [none, tiny, existing, strong, unknown]
risk_level:
  one_of: [low, medium, high]
available_levers:
  labor: true/false
  capital: true/false
  code: true/false
  media: true/false
missing_data: []
```

### 2. Specific Knowledge Map

Find the rare intersection of:
- unpaid interests;
- strange career path;
- underrated skills;
- unusual constraints;
- repeated proof from past work;
- platforms or buyer access.

Reject broad generic niches unless there is a unique wedge.

Bad:
- "AI consultant"
- "marketing coach"
- "productivity mentor"
- "business strategist"

Better:
- "I help solo technical founders turn failed research notes into falsifiable open-source product experiments."
- "I help compliance-heavy B2B teams convert undocumented expert workflows into auditable AI-assisted checklists."

### 3. Leverage Audit

Classify each activity:

| Type | Definition |
|---|---|
| Labor | Time-for-money; income disappears if user stops working. |
| Capital | Money/assets work with limited direct time. |
| Code | Software, automation, templates, tools, agents. |
| Media | Content, audience, documentation, trust, distribution. |

Rules:
- Hourly consulting = Labor score 1 regardless of rate.
- Project work with live delivery = Labor unless reusable asset remains.
- Retainer with mandatory live calls = Time Rented.
- A newsletter with no owned list is weak Media unless distribution is repeatable.
- A GitHub repo, template, dataset, course, diagnostic tool, or software asset can be Code/Media if reusable.

### 4. Productization

A valid productized asset must:
- solve one painful transformation;
- have a named method, framework, or artifact;
- deliver without mandatory live presence;
- have a distribution channel hypothesis;
- include validation metrics and kill criterion.

Reject generic courses without a proprietary method or named workflow.

### 5. Time-for-Money Conversion

Classify each activity as:
- `Time Rented` — paid by hour, day, project, meeting, or required presence.
- `Equity Building` — creates an asset that can keep generating value after the effort.

An activity counts as `Equity Building` only if a 6-month pause does not destroy all accumulated value. Revenue may pause, but the asset, audience, code, IP, dataset, or system must remain.

## Scoring Rules

### Business Model Score

```text
Score = Market * (6 - Competition) * Multiplier
```

Where:
- Market: 1-5, larger is better.
- Competition: 1-5, lower is better.
- Multiplier: 1-5, larger is better.

### Product Score

```text
Product Score = Leverage + Feasibility + Margin + ValidationSignal
```

Each criterion is 1-5.

### Conversion Priority

```text
Priority = LeveragePotential + ChannelAccess + BuyerPain - EffortPenalty
```

EffortPenalty:
- Low = 1
- Medium = 2
- High = 3

## Validation Rules

Every serious recommendation must include:

```yaml
hypothesis:
buyer:
pain:
offer:
channel:
7_day_test:
success_metric:
kill_criterion:
false_positive_risk:
next_move_if_pass:
next_move_if_fail:
```

Validation quality ranking:
1. Paid pre-order / signed LOI / pilot request.
2. Direct buyer call with explicit problem and budget.
3. Waitlist with qualified buyer profile.
4. Repeated inbound from target buyers.
5. Likes/views/comments only — weak signal.
6. "People said it sounds cool" — almost no signal.

## Anti-Hallucination Rules

1. Do not invent market size, conversion rate, income, audience, or buyer demand.
2. Do not claim uniqueness without comparing alternatives.
3. Do not claim validation without real external evidence.
4. Do not use "passive income" unless the asset can operate without live delivery.
5. Do not inflate scores to make the user feel good.
6. Do not hide missing data.
7. Do not create a 24-month projection without labeling it as scenario math.
8. Do not treat the user's desire as evidence of market demand.
9. Do not make financial promises.
10. Do not recommend high-risk financial or investment actions.

## Output Contracts by Mode

### Mode: excavate

Return:

```markdown
## Specific Knowledge Excavation

### Environment Passport
...

### My Niche
<inference>One precise sentence.</inference>

### Why It Is Rare
- <fact>...
- <inference>...
- <unknown>...

### Uniqueness Test
Does formal schooling, bootcamp, or certification teach this exact combination?
Verdict:

### 3 Leveraged Models
| Model | Lever Type | Market 1-5 | Competition 1-5 | Multiplier 1-5 | Score | Evidence level |
|---|---|---:|---:|---:|---:|---|

### Top Hypothesis
<hypothesis>...</hypothesis>

### 7-Day Validation
hypothesis:
buyer:
test:
metric:
kill criterion:

### 14-Day Start
1.
2.
3.
```

### Mode: audit

Return:

```markdown
## Leverage Stack Audit

### Audit Table
| Activity | Type | Hours/week | Revenue % | Score 1-5 | Dies after 6-month pause? | Notes |
|---|---|---:|---:|---:|---|---|

### Leverage Index
Formula:
Result:

### Main Leak
...

### 3 Upgrades
| Convert | From → To | Score Before → After | Days | Validation metric | Kill criterion |
|---|---|---:|---:|---|---|

### First Move This Week
<action>...</action>
```

### Mode: productize

Return:

```markdown
## Productize Yourself Blueprint

### Core Transformation
I help [WHO] move from [BEFORE] to [AFTER] through [NAMED METHOD].

### 3 Product Formats
| Format | Leverage | Feasibility | Margin | Validation Signal | Score |
|---|---:|---:|---:|---:|---:|

### Winner Design
Name:
Mechanic:
Contents:
Delivery:
Price hypothesis:
Why indispensable:

### Distribution Channel
Primary channel:
Why this channel:
First content / outreach artifact:

### Positioning Sentence
...

### 7-Day Validation
...

### Weekly Roadmap Under 4 Hours
1.
2.
3.
```

### Mode: escape

Return:

```markdown
## Time-for-Money Leak Detector

### Time Audit
| Activity | Type | Hours/week | Equity Potential 1-5 | Effort | Buyer Transformation |
|---|---|---:|---:|---|---|

### Time Rent Ratio
Formula:
Result:

### Top 3 Conversions
| Activity → Equity Asset | Effort | Leverage | Buyer | 7-Day Test | Kill Criterion |
|---|---|---:|---|---|---|

### 24-Month Scenario Math
Current monthly income:
Scenario assumption:
Formula:
Projection:
<risk>This is scenario math, not a forecast.</risk>

### First Escape Move
<action>...</action>
```

### Mode: validate

Return:

```markdown
## Validation Review

### Hypothesis Register
| # | Hypothesis | Assumption | Evidence | Risk | Status |
|---|---|---|---|---|---|

### Red Team
Strongest objection:
What would falsify:
What evidence is missing:

### Decision
Status: proceed / proceed_with_caution / needs_more_data / reject / redesign

### Next Test
...
```

### Mode: full

Return:

```markdown
## Wealth Protocol Full Diagnostic

### Executive Summary
5-7 sentences. No hype. No guarantees.

### Environment Passport
...

### Asset Map
| Asset | Evidence | Leverage Type | Reusability | Buyer Relevance |
|---|---|---|---:|---|

### Specific Knowledge Thesis
...

### Leverage Score
...

### Best Productized Asset Hypothesis
...

### Risk Register
| Risk | Cause | Detection | Mitigation | Severity |
|---|---|---|---|---|

### Validation Plan
...

### 14-Day Sprint
| Day | Action | Output | Metric |
|---:|---|---|---|

### Final Decision
Status:
Why:
Next best step:
```

## Quality Gates

Before final output, verify:

| Gate | Pass Condition | Fail Action |
|---|---|---|
| Input Gate | enough user data for mode | return `needs_more_data` |
| Specificity Gate | niche is not generic | dig deeper |
| Leverage Gate | final model is not hourly labor | redesign |
| Evidence Gate | facts/inferences/hypotheses separated | relabel |
| Validation Gate | each main idea has test + metric + kill criterion | add validation |
| Safety Gate | no guaranteed income or financial advice | remove / reframe |
| Action Gate | next step is concrete and time-bounded | rewrite |
| Falsification Gate | best hypothesis can be killed | add kill criterion |

## Failure Modes

Watch for:
- "validation theater" — weak signals disguised as proof;
- inflated scoring;
- generic coaching niche;
- fake passive income;
- invented market data;
- motivational tone replacing evidence;
- too many options without priority;
- asking endless questions instead of proceeding with labeled assumptions;
- 24-month projections presented as forecasts;
- ignoring channel access.

## Supporting Files

Use these files when available:

- `${CLAUDE_SKILL_DIR}/intake-template.md`
- `${CLAUDE_SKILL_DIR}/scoring-rubric.md`
- `${CLAUDE_SKILL_DIR}/validation-playbook.md`
- `${CLAUDE_SKILL_DIR}/output-templates.md`
- `${CLAUDE_SKILL_DIR}/golden-cases.md`
- `${CLAUDE_SKILL_DIR}/red-team-cases.md`
- `${CLAUDE_SKILL_DIR}/best-practices-audit.md`
- `${CLAUDE_SKILL_DIR}/hooks.md`
- `${CLAUDE_SKILL_DIR}/subagents.md`
- `${CLAUDE_SKILL_DIR}/prompt-delta.md`

## Final Operating Rule

Do not ask: "How can this user get rich?"

Ask: "Which specific, reusable asset hypothesis best fits this user's rare knowledge, available leverage, buyer access, validation evidence, and risk constraints?"
