# Skeptic Auto-Triggers — Preventing Validation Theater

## Purpose
Automatically invoke skeptic agent when claims have high risk of confirmation bias or validation theater.

## Auto-Invoke Rules (NO human approval needed)

Skeptic agent MUST be invoked when ANY of these triggers fire:

### Trigger 1: High-Confidence Claims
**Pattern:** Any statement with ≥90% confidence, "100% SUCCESS", "all X passed", "perfect score"  
**Examples:**
- "All 10 hypotheses validated"
- "F1=1.000 across all tests"
- "100% precision, 100% recall"
- "Zero failures in 50 tests"

**Why risky:** Suspiciously perfect results often indicate synthetic data or circular logic.

### Trigger 2: Unexpected Success
**Pattern:** Success rate significantly exceeds prior base rate  
**Formula:** `actual_success_rate > 2.5 × expected_base_rate`  
**Examples:**
- Expected 20% niches work → claiming 100% work = 5× base rate
- Industry benchmark 30% F1 → claiming 95% F1 = 3.2× benchmark

**Why risky:** Outlier performance needs extraordinary evidence (Sagan standard).

### Trigger 3: Zero Failures
**Pattern:** "all tests passed", "no bugs found", "no edge cases" across ≥5 independent tests  
**Examples:**
- "Tested 10 scenarios, all passed"
- "No failing test cases found"
- "All validation scripts green"

**Why risky:** Real-world data ALWAYS has edge cases. Zero failures = tests too weak or synthetic.

### Trigger 4: Round Numbers
**Pattern:** Suspiciously perfect metrics (F1=1.000, precision=1.0, recall=1.0, R²=0.99)  
**Threshold:** Metric ends in .000 or .00 AND claims real-world validation  
**Examples:**
- F1=1.000 (not F1=0.987)
- Accuracy=100% (not 98.3%)
- Correlation=0.99 (not 0.934)

**Why risky:** Real metrics are messy. Perfect decimals often indicate rounding/synthetic/cherry-picking.

### Trigger 5: Synthetic Evidence
**Pattern:** Any validation claim marked `[VERIFIED-SYNTHETIC]` OR inline test data embedded in code  
**Examples:**
- "F1=1.000 [VERIFIED-SYNTHETIC] on create_synthetic_dataset()"
- "Tested on mock data → 100% success"
- **NEW:** `python -c` or `python <<EOF` with embedded test cases (no external dataset URL)

**Detection heuristics for inline synthetic:**
```python
# Red flags in validation code:
abstracts = [("example 1", "LABEL"), ("example 2", "LABEL")]  # Embedded test cases
test_data = {"input": "...", "expected": "..."}  # Hand-crafted examples
examples = ["text 1", "text 2", ...]  # No URL/API call to fetch data

# Green flags (real data):
response = requests.get("https://api.nih.gov/grants")  # External API
df = pd.read_csv("real_data.csv")  # External file with URL cited
```

**Why risky:** Synthetic tests prove code runs, NOT that it works on real data (tautology).  
Inline synthetic is HARDER to detect than file-based (no `create_synthetic_dataset()` function name).

---

## Skeptic Protocol (when triggered)

**Step 1: Log trigger**
```
[SKEPTIC-TRIGGER] Detected: {trigger_name}
Claim: {original_claim}
Evidence: {evidence_provided}
Code analyzed: {python_heredoc OR file_path}
```

**Step 1.5: Detect inline synthetic data (NEW)**
If validation uses `python -c` or heredoc (`python <<EOF`):
- **Scan for embedded test data:** `abstracts = [...]`, `test_cases = {...}`, `examples = ["..."]`
- **Check for external data source:** `requests.get()`, `pd.read_csv()`, API calls
- **If NO external source AND F1 ≥ 0.9:** Flag as [SYNTHETIC-INLINE]

**Step 2: Generate falsification tests**
Create 3 real-world test cases designed to BREAK the claim:
1. Adversarial example (edge case)
2. Real-world data (external source, not project-generated)
3. Independent reproduction (different dataset/method)

**For inline synthetic detection:**
- Replace embedded test cases with REAL API call (e.g., NIH RePORTER, Enron Corpus URL)
- Re-run validation
- If F1 drops → claim [FALSIFIED-INLINE-SYNTHETIC]

**Step 3: Run tests**
Execute all 3 falsification tests. Record results.

**Step 4: Report**
Return ONE of:
- `[CONFIRMED-REAL]` — all 3 falsification tests passed, claim holds on real data
- `[FALSIFIED]` — ≥1 test failed, claim does not hold, cite failure case
- `[NEEDS-REAL-DATA]` — cannot test (no real data available), claim suspended until validated
- `[WEAKENED]` — claim holds but with caveats (lower confidence, narrower scope)

---

## Implementation (Orchestrator Integration)

```python
# Add to orchestrator before declaring success

SKEPTIC_TRIGGERS = [
    lambda claim: any(word in claim.lower() for word in ["100%", "all", "zero", "perfect"]),
    lambda claim: "F1=1.000" in claim or "precision=1.0" in claim,
    lambda claim: "[VERIFIED-SYNTHETIC]" in claim,
    lambda claim: re.search(r'\d+\.\d{3,}0', claim),  # Round numbers
]

def before_success_declaration(claim: str, evidence: list[str]) -> None:
    """Check skeptic triggers before presenting high-confidence claims."""
    
    triggered = [i for i, trigger in enumerate(SKEPTIC_TRIGGERS) if trigger(claim)]
    
    if triggered:
        logger.warning(f"Skeptic triggers fired: {triggered} for claim: {claim[:100]}")
        
        # Invoke skeptic agent (Agent tool, subagent_type="skeptic")
        skeptic_result = invoke_skeptic_agent(
            prompt=f"Falsification test for claim: {claim}\nEvidence: {evidence}",
            description="Auto-triggered skeptic audit"
        )
        
        if skeptic_result.verdict == "FALSIFIED":
            raise ValidationError(
                f"Skeptic BLOCKED claim: {claim}\n"
                f"Falsification case: {skeptic_result.failure_case}"
            )
        
        # Append skeptic verdict to evidence
        evidence.append(f"[SKEPTIC-AUDITED] {skeptic_result.verdict}")
```

---

## Escape Hatches (Override Only with Justification)

Skeptic trigger can be bypassed ONLY if:

1. **Pilot study** — explicitly marked as "preliminary" or "proof-of-concept"  
   Override tag: `[PILOT-ONLY]`

2. **Documented limitation** — claim explicitly states "synthetic data" in main text  
   Override tag: `[SYNTHETIC-ACKNOWLEDGED]`

3. **Time-critical** — production incident, must act now, validate later  
   Override tag: `[DEFER-SKEPTIC]` + create ticket to validate post-incident

**Never override:** Production validation claims, customer-facing metrics, ROI estimates.

---

## Success Metrics

Track effectiveness:
- **Caught validation theater:** # of [FALSIFIED] verdicts
- **False positives:** # of [CONFIRMED-REAL] after trigger (acceptable)
- **Missed failures:** # of user-caught issues that didn't trigger skeptic (minimize)

**Goal:** User never catches validation theater before skeptic does.

---

## Example: Skeptic Would Have Caught ТОП-10 Theater

**Claim (2026-05-01):** "All 10 niches validated, 100% SUCCESS"

**Trigger fired:** Trigger 1 (100% success), Trigger 3 (zero failures), Trigger 5 (synthetic evidence)

**Skeptic falsification tests:**
1. Run H2 Legal validator on REAL Enron emails (not synthetic)  
   → Result: F1=0.500 (missed 50% of cases) → [FALSIFIED]

2. Run H7 Insider Trading on real SEC filings  
   → Result: F1=0.000 (complete failure) → [FALSIFIED]

3. Check if validators cite external data sources  
   → Result: All use create_synthetic_dataset() → [NEEDS-REAL-DATA]

**Skeptic verdict:** `[FALSIFIED]` — claim does not hold on real data

**Action:** Block "100% SUCCESS" declaration, require real-world validation

**Outcome:** Saves $1.4M disaster (postmortem estimate)

---

**Last updated:** 2026-05-01  
**Status:** ACTIVE — enforced in orchestrator workflow
