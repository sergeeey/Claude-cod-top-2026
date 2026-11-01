# Worked examples

Read this file only when the task is ambiguous or when an example would clarify the method. The examples are illustrations of structure. Only Example 2 uses real project facts; it is labelled as such.

---

## Example 1 — Software: adopting an AI coding tool across a team (illustrative)

**S0 (current state).** A product team of eight developers works on a service with a large test suite and a legacy module. Adoption of an AI assistant is at the level of individual use.

**Trigger.** TECHNOLOGY_CHANGE: the team lead decides to enable the assistant for all developers, and the vendor cuts the price per seat.

**Baseline (no new intervention).** Individual use continues. Team velocity changes slowly. Technical debt in the legacy module keeps growing at its current rate.

**Core mechanisms.**
- M1: the marginal cost of a code change falls, so more changes are proposed.
- M2: review and test capacity do not grow with the number of changes.
- M3: developers who stop practising a skill lose the ability to judge the output.

**Trajectories.**

```
S0
├─ T1: more output, review keeps up
│   ├─ mechanism: M1 + added automated checks
│   └─ lag: weeks
│   → S1: higher throughput, stable defect rate
│       signpost: defect rate and review time both stay flat for two months
│
├─ T2: more output, review becomes the bottleneck
│   ├─ mechanism: M1 + M2, expectations rise
│   ├─ lag: one to three months
│   → S2: the earlier productivity gain becomes the new baseline, reviewers overloaded
│       signpost: review queue length grows; merge time rises
│
└─ T3: skill erosion in selected tasks
    ├─ mechanism: M3, lag: months to years
    → S3: the team depends on the assistant for debugging; slower incident response when it fails
        signpost: fewer unassisted fixes in incident reviews
```

**External trigger.** A competitor ships faster. The advantage of T1 becomes the minimum for parity, which is a reference shift: the baseline moves.

**Delayed effect.** T1 can look good for a quarter and later create lock-in: tooling, workflows and expectations built around the assistant. Changing it later is costly.

**Distinguishing observation.** Review queue length over eight weeks. If it grows while throughput grows, T2 is starting. If it stays flat, the T2 signpost is not met, and T1 is supported relative to T2.

**Residual uncertainty.** Vendor pricing and model quality may change. Team morale and hiring are not modelled.

---

## Example 2 — Research: an ETL research line after a null verdict (real project, verified facts)

**S0 (current state, as of 2026-10-29).**
- VERIFIED: `validity_gates.json` dated 2026-08-15 has overall FAIL; V4 and V6 fail, the other six gates pass.
- VERIFIED: `docs/experiment1_rq1_preliminary_report.md` states RQ1 status NOT_SUPPORTED, decided by hand, and admits V4 and V6 do not satisfy the literal rule.
- VERIFIED: the verdict is not linked to gate status in code, and the preregistration hash is written but not checked on read.
- VERIFIED: git HEAD is `edd7a77` (2026-09-07). Several support files are uncommitted.
- UNKNOWN: whether the gate results still hold; the file is more than two months old.
- INFERRED: the source code in `src/` has not changed since the HEAD commit, so the gates were produced by current code.

**Trigger.** ACTION pending: the owner decides whether to add a rule that links the verdict to gate status (an OVERRIDE rule) and whether to re-run gates.

**Baseline (no new intervention).** The support files stay uncommitted, RQ1 stays in the documents, the line drifts to the archive. This is a comparison path, not a forecast.

**Mechanisms.**
- M1: the verdict stays a prose claim that the code does not check, so a later reader can cite NOT_SUPPORTED without the FAIL.
- M2: re-running the same confirmatory data after the gate failed is post hoc unless the change is a documented bug fix. The preregistration and the EstimandOps rule forbid silent threshold changes.
- M3: a diagnostic on existing data (for example, V6 stratified by world family) can explain the failure without changing any threshold, but it is exploratory.

**Trajectories.**

```
S0
├─ T1: fix the tooling, re-run the gates on the same data
│   ├─ mechanism: the verdict is linked to the gate; V6 stratified diagnosis
│   ├─ lag: days to weeks
│   ├─ counterforce: changing V4 or V6 after the failure is post hoc (M2)
│   → S1a: V6 passes after a documented bug fix; RQ1 gets a gate-backed verdict
│   → S1b: V6 still fails; NOT_SUPPORTED becomes gate-backed and stronger
│   signpost: a commit touching verdict code; a new validity_gates.json with a new timestamp
│
├─ T2: keep the verdict and test a new world family
│   ├─ mechanism: a world whose true mechanism lies outside the hypothesis set
│   ├─ lag: weeks to months
│   → S2a: B3 beats B0 out of the closed world; the null becomes conditional on the ontology
│   → S2b: B3 does not beat B0; the null strengthens
│   signpost: a new data folder with a different world family; a new primary comparison
│
└─ T3: archive with caveats
    ├─ mechanism: the line closes; the verdict is reused as a final negative
    ├─ lag: immediate
    → S3: the project is parked; RQ1 is cited elsewhere
    ├─ delayed effect (M1): a later citation without gate status makes an unfinished result look final
    signpost: a document citing RQ1 without the gate status

Baseline: no commit for thirty days; support files stay uncommitted.
```

**Counterevidence and fragile assumptions.**
- For T1 to matter, the V6 failure must be partly an artefact of the family mix. The report's section 2.6 suggests partial support. This is not established.
- For T2 to matter, the hypothesis-set closure must be the limiting factor. The specification names the general risk of synthetic ontology, not this specific mechanism.

**Distinguishing observation.** A stratified V6 result by world family, computed without changing thresholds. If the failure concentrates in one family, T1 is the more informative path. If it is spread evenly, T2 is more informative.

**Residual uncertainty.** The owner's priorities and time. The gate status after August. Other repositories, which were not scanned.

**Next observation.** The answer to the OVERRIDE question. It costs nothing and decides which branch is open.

---

## Example 3 — Business: a small firm cuts prices by 10% to win share (illustrative)

**S0.** A firm with 40 customers, 3 months of cash reserve, and a contract with one supplier that has a minimum-volume clause.

**Trigger.** ACTION: a 10% price cut to win share from a rival.

**Response of the world (not the same as the action).**
- O1: the rival matches the cut, and both firms lose margin.
- O2: the rival does not match, and the firm gains share.
- O3: the rival matches and adds a service the firm cannot copy quickly.

**Mechanisms and lags.**
- Margin compression is immediate; share gain takes one to two quarters.
- Customer price expectations reset downwards. Raising the price later is a visible reversal: this is a path-dependent effect.
- The minimum-volume clause ties the firm to the supplier. Extra volume from share gain is safe; a volume drop would hit cash.

**Trajectories.** O2 is the only branch where the action reaches its aim. O1 and O3 each reduce the gain, through different mechanisms. The signposts below separate them. This is a conditional map: no likelihood is assigned, since no base rate is available.

**Signposts.** Rival pricing in the next two quarters; customer churn; supplier volume against the minimum; the firm's cash runway in months.

**Delayed effect.** Lower expectations persist after the price war ends. Reversing the price becomes costly.

**Residual uncertainty.** Competitor intent is unknown. Customer loyalty is not measured.

---

## Example 4 — Technology: a sharp fall in model API prices (illustrative)

**S0.** A company builds its product on a paid model API. Its cost structure assumes the current price.

**Trigger.** TECHNOLOGY_CHANGE: the price falls by a large factor.

**Reference shift.** The old baseline cost no longer describes the market. Competitors can offer features the company priced out. The comparison point has moved, so "we are competitive" must be checked against the new reference.

**Mechanisms.**
- M1: lower cost makes more features economical.
- M2: the company's advantage shrinks when rivals reach the same features in a short time.
- M3: a dependence on one vendor persists even when prices fall; a price rise later would hurt again.

**Trajectories.**
- T1: the company uses the saving to build features faster; margin holds; the lead depends on distribution, not model cost.
- T2: the company keeps its old price; competitors take share.
- T3: the company diversifies vendors; lock-in falls; integration cost rises for a while.

**Signposts.** Feature release pace; churn to rivals; the share of revenue spent on model calls; number of vendors in production.

**Delayed effect.** Price falls can reverse if the market consolidates. Vendor dependence (M3) is a structural effect that the saving can hide for a year.

**Residual uncertainty.** Future price direction; quality changes; regulation of model access.

---

## Example 5 — Geopolitics: export restrictions on a commodity (illustrative, no real facts)

**S0.** A country depends on imports of a processed material. It has some domestic capacity and two possible suppliers.

**Trigger.** RULE_CHANGE: a major exporter introduces export limits.

**Baseline (no new intervention).** Trade continues under the old rules until the limits take effect. Stocks deplete at the current rate.

**Actors.** The exporter (may tighten or relax), the importing government (may subsidize domestic capacity or buy from a third country), the domestic industry (may lobby or invest), third-country suppliers (may raise capacity if prices rise).

**Mechanisms and lags.**
- M1: the price rises immediately; domestic capacity takes years to build.
- M2: third-country suppliers respond within months, but quality and contracts take longer.
- M3: a subsidy changes incentives and may create overcapacity that persists after the crisis.

**Trajectories.**
- T1: the importer buys from a third country; costs rise; the dependence is partly replaced.
- T2: the importer subsidizes domestic capacity; output starts in years; overcapacity risk later (M3).
- T3: the limits are relaxed under negotiation; the old map returns, with a new precedent that the rules can change.

**External trigger.** A regional conflict that closes a route. This changes the options of every branch.

**Signposts.** Import volumes by source country; contract announcements from third suppliers; subsidy programmes; the exporter's official statements.

**Residual uncertainty.** Political decisions that cannot be modelled; the exporter's domestic politics.

---

## Example 6 — Project decision: release a tool publicly or keep it private (illustrative)

**S0.** An author has a working research tool, a small user base, and no maintenance budget. A public release would bring feedback and risk.

**Trigger.** ACTION: public release.

**Responses of the world.**
- O1: users adopt it and report bugs; maintenance load grows.
- O2: little attention; the release is quiet and the tool stays a side project.
- O3: a rival project copies the idea with more resources.

**Path dependence.** A public release creates commitments: users expect fixes, and the API becomes hard to change. A private tool has no such commitments and keeps options open.

**Trajectories.**
- T1: O1, growing maintenance; commitment rises; the author either invests or abandons it publicly (a reputational cost).
- T2: O2, a quiet release; the cost is low and the learning is limited.
- T3: O3, a race; the author's advantage depends on prior publication and documentation.

**Delayed effect.** Maintenance debt appears after the first wave of attention, not at release.

**Signposts.** Issues opened per week; contributors who are not the author; whether a rival appears within six months.

**Residual uncertainty.** Attention is unpredictable; the author's time over the next year is not fixed.
