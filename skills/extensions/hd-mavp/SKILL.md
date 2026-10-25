---
name: hd-mavp
version: 1
description: >
  HD-MAVP (Hypothesis Decomposition - Multi-Axis Verification Protocol).
  Activate when the user wants to decompose, audit, verify, or stress-test
  a scientific paper, preprint, theory, hypothesis, model, or any structured
  claim. Trigger phrases: "decompose", "аудит", "декомпозиция", "разложи",
  "проверь гипотезу", "карта хрупкости", "brittleness map", "analyze claims",
  "audit paper", "verify theory", "atomic decomposition", "claim matrix".
argument-hint: "<path or text of document/hypothesis to decompose>"
triggers: [hd-mavp, /hd-mavp, hd, mavp, Hypothesis, Decomposition, Multi, Axis, Verification]
---

# HD-MAVP: Hypothesis Decomposition — Multi-Axis Verification Protocol

## When to activate
Activate for any document, theory, preprint, model, or structured claim where
the user wants to understand: what is asserted, what is proven, what is assumed,
what is the weakest point, and what would falsify the whole structure.

---

## Protocol Overview

The protocol has 6 phases. Always execute in order. Never skip Phase 0.

```
Phase 0 → Ingest + Classify
Phase 1 → Trunk/Branch/Leaf Mapping (Anatomy)
Phase 2 → Atom Decomposition (Postulate / Claim / Derivation)
Phase 3 → Verification Matrix (CONFIRMED / OPEN / REJECTED / BLOCKER)
Phase 4 → Brittleness Map (🔴 Critical / 🟡 Moderate / 🟢 Robust)
Phase 5 → Attack Vectors (questions for author / falsification tests)
```

---

## Phase 0 — Ingest + Classify

Read the full document. Then produce a 3-line summary:
- **What is claimed** (one sentence, falsifiable)
- **What evidence is provided** (data type: observational / theoretical / numerical)
- **What is NOT provided** (missing derivation, missing data, missing mechanism)

---

## Phase 1 — Trunk / Branch / Leaf Anatomy

Map the logical architecture as a 3-level hierarchy.

| Level | Name | Definition | Example |
|---|---|---|---|
| Trunk | Core Postulate | Foundational assumption; unprovable in the paper itself | "The system obeys conservation law X" |
| Branch | Mid-level Claim | Derived from Trunk; testable in principle | "Quantity Y can be computed from X" |
| Leaf | Specific Assertion | Concrete numerical / observational result | "Parameter k = 4.5 fits Table 2" |

**Output format:**
```
T1 (Trunk): [statement]
  ├─ B1 (Branch): [statement]  ← depends on T1
  │    ├─ L1 (Leaf): [statement]  ← depends on B1
  │    └─ L2 (Leaf): [statement]
  └─ B2 (Branch): [statement]
       └─ L3 (Leaf): [statement]
```

---

## Phase 2 — Atom Decomposition Table

Break the theory into atoms. Each atom is a single, indivisible logical unit.

**Atom types:**
- **[A] Assumption** — stated or unstated; taken on faith; not derived
- **[C] Claim** — asserted to be derivable or proven
- **[D] Derivation** — mathematical/logical step shown in the paper
- **[N] Numerology** — numerical coincidence without mechanistic justification
- **[GAP]** — logical step the paper requires but does not provide

**Table format:**

| ID | Type | Statement | Source (eq/section) | Verifiable? | Notes |
|---|---|---|---|---|---|
| A1 | [A] | ... | §1 postulate | No | Core axiom |
| C2 | [C] | ... | §3 claim | In principle | Requires bridge |
| D3 | [D] | ... | Eq. 7 | Yes | Math correct |
| N4 | [N] | ... | Table 1 | Numerically only | Missing mechanism |
| G5 | [GAP] | ... | Step 5→6 | ❌ | Missing formula |

**Rules:**
- Every atom gets a unique ID (A-trunk, B-branch alphabetically, numbered)
- Maximum one statement per row
- "Verifiable?" = can we verify this NOW without asking the author?
- Distinguish [C] from [D]: a Claim says "this follows" but doesn't show steps; a Derivation shows steps

---

## Phase 3 — Verification Status Matrix

For each atom from Phase 2, assign a status based on available evidence.

**Status labels:**

| Status | Meaning |
|---|---|
| ✅ CONFIRMED | Independently verified; math checks out |
| ⚠️ OPEN | Not yet verified; needs data or author clarification |
| ❌ REJECTED | Verified to be false or internally inconsistent |
| 🔴 BLOCKER | Cannot proceed without resolving; blocks reproduction |
| 🔢 NUMEROLOGY | Numbers fit but no mechanism — epistemically weak |
| 👻 AI-HALLUCINATED | Step was filled by an AI service, not the author |

**Output format:**

| Atom ID | Status | Evidence for | Evidence against | Blocking what? |
|---|---|---|---|---|
| A1 | ✅ CONFIRMED | cited reference + independent recalculation | — | — |
| G5 | 🔴 BLOCKER | — | independent reproductions give different results | Table reproduction |

---

## Phase 4 — Brittleness Map

Identify structural vulnerabilities. A node is "brittle" if removing it collapses
a significant portion of the theory.

**Brittleness levels:**
- 🔴 **CRITICAL** — removing this kills the main result; no workaround
- 🟡 **MODERATE** — removing this weakens one branch; others survive
- 🟢 **ROBUST** — well-supported; survives independent challenge

**Map format:**

```
BRITTLENESS MAP
═══════════════

🔴 CRITICAL NODES (theory collapses without these):
  [1] <Atom ID>: <why critical>
      Impact: <what breaks>
      Cascade: <dependent atoms>
      Recovery path: <what would fix this>

🟡 MODERATE NODES (one branch weakens):
  [3] <Atom ID>: <why moderate>

🟢 ROBUST NODES (independently verified):
  [5] <Atom ID>: <why robust>
```

---

## Phase 5 — Attack Vectors

Generate precise, testable questions that would either falsify or strengthen the theory.

### 5A. Author Questions (require insider knowledge)
```
Q1: [Exact question]
    Tests atom: [ID]
    Expected if theory is correct: [answer]
    Expected if gap exists: [answer]
```

### 5B. Independent Verification (can be done without author)
```
V1: [What to compute/check]
    Atoms tested: [IDs]
    Tool: [Python / literature / simulation]
    Exit condition: [what result would CONFIRM / REJECT]
```

### 5C. Falsification Tests (killshots)
```
F1: [Specific prediction the theory makes]
    Observation that would falsify it: [...]
    Current data: [consistent / inconsistent / unknown]
```

---

## Output Structure

Produce all 5 phases in one response. Use these exact headers:

```
## HD-MAVP Analysis: [Document Title]

### Phase 0: Ingest Summary
### Phase 1: Architecture Map
### Phase 2: Atom Decomposition
### Phase 3: Verification Matrix
### Phase 4: Brittleness Map
### Phase 5: Attack Vectors
### Score Card
```

**Score Card template:**
```
SCORE CARD
══════════
Atoms total:            XX
  Confirmed:            XX (XX%)
  Open:                 XX (XX%)
  Rejected/Blocker:     XX (XX%)
  Numerology/AI-Gap:    XX (XX%)

Critical brittle nodes: X
Reproducible without author: YES / PARTIAL / NO

Audit verdict:
  REPRODUCIBLE       — all key steps verifiable
  CONDITIONAL        — reproducible if author answers Q1-QN
  BLOCKED            — structural gaps prevent reproduction
  REJECTED           — internally inconsistent
```

---

## Adaptive Extensions

Based on document type, add Phase 6 automatically:

| Document type | Phase 6 content |
|---|---|
| Physics/cosmology preprint | Dimensional analysis check on all equations |
| Statistical model | Degrees-of-freedom and overfitting audit |
| AI/ML paper | Benchmark reproducibility and data leakage check |
| Economic model | Parameter sensitivity (±10% perturbation table) |
| Historical/archival claim | Source chain verification |
| Any paper using AI tools | AI-hallucination audit (which steps were AI-generated?) |
| Software/code | Reproducibility: can the code be run from scratch? |

---

## Quality Rules

1. **Every atom must be falsifiable in principle** — if no evidence could reject it, it is a definition
2. **[GAP] ≠ [A]** — a Gap is missing derivation; an Assumption is a stated axiom
3. **Numerology must be flagged** — numerical coincidence without mechanism is NOT a strong point
4. **AI-generated steps must be marked** 👻 — if AI filled a methodological gap, tag it
5. **Brittleness is structural, not stylistic** — judge by logical dependency, not author confidence
6. **Score honestly** — a 60% confirmation rate with one critical blocker is BLOCKED, not "mostly ok"
7. **Epistemology ≠ Mathematics** — correct math does not imply correct physics; flag both separately
