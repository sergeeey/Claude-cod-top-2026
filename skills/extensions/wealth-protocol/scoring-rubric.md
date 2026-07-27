# Wealth Protocol Scoring Rubric

Use scores to compare hypotheses, not to pretend certainty.

All scores are provisional unless backed by external evidence.

## 1. Market Score

| Score | Meaning |
|---:|---|
| 1 | Tiny, unclear, or not economically painful. |
| 2 | Narrow but real; buyer budget uncertain. |
| 3 | Clear niche with some budget. |
| 4 | Strong pain, identifiable buyers, existing spend. |
| 5 | Urgent, budgeted, repeated pain with many reachable buyers. |

## 2. Competition Score

Lower is better.

| Score | Meaning |
|---:|---|
| 1 | Few visible alternatives; strong unique angle. |
| 2 | Alternatives exist, but user's angle is differentiated. |
| 3 | Moderate competition; differentiation required. |
| 4 | Crowded category with many competent providers. |
| 5 | Commodity market; hard to stand out. |

## 3. Multiplier Score

| Score | Meaning |
|---:|---|
| 1 | Requires direct human delivery each time. |
| 2 | Some templates/process reuse. |
| 3 | Repeatable productized service or cohort asset. |
| 4 | Software/media/automation can scale with low marginal cost. |
| 5 | Code/media/capital loop improves with use and distribution. |

## 4. Leverage Score

| Score | Meaning |
|---:|---|
| 1 | Pure time-for-money. |
| 2 | Reusable process but still live delivery. |
| 3 | Productized service with limited live component. |
| 4 | Digital product, tool, content library, or automation. |
| 5 | Zero/near-zero marginal cost asset with distribution. |

## 5. Feasibility Score

Score feasibility for a 30-day prototype.

| Score | Meaning |
|---:|---|
| 1 | Not feasible without major resources. |
| 2 | Possible but requires major scope cuts. |
| 3 | Feasible MVP with discipline. |
| 4 | Feasible with existing assets. |
| 5 | Can be built from existing materials in days. |

## 6. Margin Score

| Score | Meaning |
|---:|---|
| 1 | Low margin; heavy labor or external costs. |
| 2 | Moderate margin but manual delivery. |
| 3 | Good margin with some delivery burden. |
| 4 | High margin; mostly reusable. |
| 5 | Very high margin; low marginal cost. |

## 7. Equity Potential

| Score | Meaning |
|---:|---|
| 1 | No asset remains after delivery. |
| 2 | Some process knowledge remains. |
| 3 | Reusable asset or audience grows slowly. |
| 4 | Asset compounds through code/media/data. |
| 5 | Durable system, brand, tool, dataset, IP, or distribution channel. |

## 8. Validation Signal

| Score | Meaning |
|---:|---|
| 1 | No evidence beyond user's belief. |
| 2 | Social interest: likes, comments, praise. |
| 3 | Direct buyer conversations confirm pain. |
| 4 | Waitlist, LOI, pilot request, or budget signal. |
| 5 | Paid pre-order, paid pilot, or repeat demand. |

## 9. Effort

| Label | Meaning | EffortPenalty |
|---|---|---:|
| Low | Can test in 1-3 days using existing assets. | 1 |
| Medium | Needs 1-2 weeks of focused work. | 2 |
| High | Needs new infrastructure, audience, or major build. | 3 |

## Core Formulas

```text
Business Model Score = Market * (6 - Competition) * Multiplier

Product Score = Leverage + Feasibility + Margin + ValidationSignal

Conversion Priority = LeveragePotential + ChannelAccess + BuyerPain - EffortPenalty
```

## Interpretation

| Result | Meaning |
|---|---|
| High score + weak evidence | Attractive hypothesis, not validated. |
| Medium score + strong evidence | Often better than fantasy high score. |
| High leverage + no channel | Needs distribution test first. |
| High feasibility + low buyer pain | Avoid building too early. |
| Low effort + high buyer pain | Test immediately. |
