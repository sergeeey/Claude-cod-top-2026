# Validation Playbook

The Wealth Protocol is validation-first.

No product, niche, or business model is proven until external evidence exists.

## Hypothesis Card

Use this template for every serious idea:

```yaml
id:
hypothesis:
buyer:
pain:
current_alternative:
offer:
asset_format:
channel:
why_now:
evidence_so_far:
unknowns:
7_day_test:
success_metric:
kill_criterion:
false_positive_risk:
next_if_pass:
next_if_fail:
owner:
date:
```

## 7-Day Validation Sprint

### Day 1 — Narrow the buyer

Output:
- one buyer segment;
- one painful transformation;
- one current alternative.

Metric:
- buyer profile is specific enough to find 20 names.

Kill criterion:
- cannot name 20 plausible buyers.

### Day 2 — Build evidence artifact

Choose one:
- landing page;
- GitHub repo;
- case study;
- diagnostic checklist;
- benchmark;
- short demo video;
- one-page offer.

Metric:
- artifact explains before/after transformation in under 60 seconds.

Kill criterion:
- target buyer cannot understand the offer.

### Day 3-4 — Distribution test

Choose one:
- 20 direct outreach messages;
- 3 buyer calls;
- 1 public post in buyer-dense channel;
- 1 demo shared in relevant community.

Metric:
- at least 3 qualified replies or 1 buyer call.

Kill criterion:
- zero qualified replies after targeted outreach.

### Day 5 — Buyer conversation

Ask:
1. What are you using now?
2. What is the cost of the problem?
3. What happens if you do nothing?
4. Who owns the budget?
5. What would make this a no-brainer?
6. Have you paid for a solution before?

Metric:
- explicit pain + current spend + next step.

Kill criterion:
- buyer says "interesting" but has no painful current alternative.

### Day 6 — Offer test

Ask for a concrete commitment:
- paid pilot;
- LOI;
- waitlist with role/company;
- intro to decision-maker;
- follow-up demo.

Metric:
- commitment stronger than praise.

Kill criterion:
- only compliments, no next action.

### Day 7 — Decision

Status:
- `proceed` — strong external signal.
- `proceed_with_caution` — signal exists but risk remains.
- `needs_more_data` — not enough buyer evidence.
- `redesign` — pain exists but offer wrong.
- `reject` — no buyer pain or no channel.

## Signal Quality Ladder

| Signal | Quality |
|---|---|
| Paid pilot | Very strong |
| Pre-order | Very strong |
| Signed LOI | Strong |
| Buyer call + budget confirmation | Strong |
| Qualified waitlist | Medium |
| Public comments from target buyers | Weak-medium |
| Likes, stars, generic praise | Weak |
| Friends say "cool idea" | Very weak |

## Anti-Patterns

Avoid:
- building for 30 days before talking to buyers;
- interpreting likes as demand;
- surveying non-buyers;
- generic "founders" or "creators" as buyer segment;
- testing with friends outside target market;
- using LLM-generated market analysis as evidence;
- moving goalposts after a failed test.

## Validation Output

```markdown
## Validation Decision

Status:

Evidence:

Metric:

What passed:

What failed:

Main risk:

Next step:

Kill / continue condition:
```
