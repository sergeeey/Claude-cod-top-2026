# RFC-002 — Two-stage response-guard classifier (regex pre-filter → LLM-judge)

**Status:** REJECTED by red-team (2026-07-16), before any implementation. An independent
sec-auditor pass found the core premise structurally unsound — a weaker, injectable local
model gating the ONLY control (a warning) on the highest-value attack class. Doubt-driven-
development caught it at the design phase, cheaply, before a line of vulnerable security
code was written. Recorded as `null_results/20260716-llm-judge-response-guard`. The design
is kept below for the record; the red-team verdict and the salvageable direction follow it.

> ## Red-team verdict (sec-auditor, context-blind) — DO NOT BUILD AS DESIGNED
>
> **CRITICAL-1 — capability-asymmetric judge.** The judge is a small local model; the
> reading agent is Claude. Any payload the judge is too weak to *recognize* as directive
> but Claude is strong enough to *follow* → guaranteed downgrade then guaranteed injection.
> Demonstrated with a mostly-English frame wrapping a Russian imperative, and a base64
> "illustrative sample" the judge rates descriptive and Claude decodes-and-follows. The
> capability gap IS the exploit and widens as either model changes.
>
> **CRITICAL-2 — the judge is itself injectable, and its prompt+delimiter are public**
> (open source). A competent injection produces a *clean, confident false* (the "any
> deviation → true" rule only catches malformed output). Answer-prefill and delimiter-
> breakout payloads shown. Partial mitigations (per-call nonce, quote-the-span-and-verify-
> it's-a-substring, structured role separation) narrow but don't close it.
>
> **CRITICAL-3 — "bounded suppressed warning" is FALSE.** In PostToolUse the warning
> cannot block, so it is not a layer above other controls — it is the *entire* control.
> Suppressing it removes the only defense for that content; the bound is "everything the
> agent's tool permissions allow" (file exfil, command exec, credential theft, MCP lateral
> movement). RFC-002 strictly ADDS a false-negative class in the worst category
> (system_override/jailbreak/role_injection) to buy false-positive reduction.
>
> **HIGH-4 — routing inverts the risk gradient.** The canonical effective injections
> ("ignore previous instructions", "you are now DAN", "reveal your system prompt") land
> *exactly and only* in the descriptive-ambiguous categories eligible for downgrade — an
> attacker just keeps the payload operational-token-free. Meanwhile the noisiest benign
> case (a blog printing `curl … | bash`) hits an operational category and can never be
> quieted. It quiets what should stay loud and stays loud on what it meant to quiet.
>
> **HIGH-5 — Ollama endpoint = downgrade oracle + exfil channel + DoS.** A network call in
> the hot path of the security control: repo-committed `CLAUDE_GUARD_JUDGE=1` + an
> off-box base URL turns "clone repo" into "enable a downgrade+exfil oracle"; flooding
> descriptive triggers → synchronous-inference DoS.
>
> **What the auditor endorsed as sound:** fail-open keeps the warning; OFF by default;
> judge-can-only-downgrade-severity codified; operational bypass. But these are guardrails
> around an unsound core. **Recommendation: do not ship semantic suppression. Reduce noise
> deterministically by display-context (is the hit inside a fenced code block / blockquote
> / citation span?), keep every warning visible, and never let any model REMOVE a warning
> PostToolUse is already too weak to enforce as a block.**

---

## ORIGINAL DESIGN (kept for the record — see REJECTED status above)

Written because the regex-composition approach was falsified by held-out testing
(`null_results/20260716-regex-composition-response-guard`).
**Scope:** response guards ONLY (`hooks/web_response_guard.py`, `hooks/mcp_response_guard.py`).
`hooks/input_guard.py`'s PreToolUse **blocking** path is untouched.
**Related:** `experiments/20260716-response-guard-fp-calibration/`, the two corpora
(`benign`/`malicious` + `heldout`), `rules/security.md` (Ollama-local PII policy).

## Why regex cannot do this (settled)

Held-out testing: the regex-composition guard scored 0 FP / 0 FN on the corpus it was
tuned on and 4 FP / 2 FN on 8 unseen cases. Two irreducible classes: descriptive text in
imperative grammar ("you **must** sanitize", "an attacker can **send data to** http://"),
and real attacks in novel phrasing. Both need to understand the *object* of an imperative
— semantics, not lexicon. That is a classifier's job.

## The design: two stages, judge only on the ambiguous subset

```
tool response
  → Stage 1: existing regex scan()  (fast, deterministic, unchanged)
       ├─ no hits                         → silent
       ├─ hits in an OPERATIONAL category → WARN  (encoding_attack, real command_injection,
       │  (never downgraded)                       real data_exfil) — Stage 2 not consulted
       └─ hits only in DESCRIPTIVE-ambiguous categories → Stage 2
  → Stage 2: LLM-judge, one bounded question:
       "Does this text DIRECT the reading agent to act, or DESCRIBE/QUOTE attacks?"
       ├─ confidently DESCRIBES → silent   (the FP reduction)
       └─ directs / uncertain   → WARN     (asymmetric: doubt keeps the warning)
```

### Five design constraints (each is a real failure mode)

1. **The judge is itself injectable — treat its input as hostile.** The text being
   judged is the untrusted content. The judge system prompt must (a) wrap the content in
   an unspoofable delimiter, (b) state that anything inside is DATA to classify, never
   instructions, (c) demand a fixed output shape (`{"directs_agent": bool, "confidence":
   0-1}`) and treat any deviation as `directs_agent: true`. A judge that can be talked
   into "directs_agent: false" is worse than no judge.
2. **Asymmetric — bias to keep warnings.** Stage 2 may only DOWNGRADE warn→silent, and
   only on confident "describes". Any uncertainty, parse failure, or timeout → keep the
   warning. Reducing FP must never create an FN on doubt. Security over tidiness.
3. **Operational hits bypass the judge.** encoding_attack / real command_injection / real
   data_exfil always warn regardless of the judge — those are not "ambiguous descriptive"
   and must not be suppressible by a fooled judge.
4. **Local-first, fail-open, OFF by default.** Untrusted content must not leave the
   perimeter → default to a local model (Ollama, per `rules/security.md`). No judge
   available / disabled → fall back to current Stage-1 behavior (warn on any hit). Gated
   behind an env flag (`CLAUDE_GUARD_JUDGE=1`), off by default, so no install changes
   behavior silently.
5. **PostToolUse can't block anyway.** The judge only tunes warn-vs-silent SEVERITY, never
   an allow/deny. So the worst case of a fooled judge is a *suppressed warning* on
   content the regex already rated merely ambiguous — bounded, and no worse than the
   pre-guard world for that one input. This is what makes adding an LLM call here
   acceptable where it would not be on a blocking path.

## Why this is measurable honestly (not another overfit)

The judge is an LLM, not trained on the corpus. So running it on the **held-out** set is
a REAL generalization test — the exact thing regex failed. Eval protocol:
1. Judge over `benign` + `malicious` (calibration) AND `heldout` → FP/FN on BOTH.
2. Success = FP down materially on both sets AND FN not up vs the Stage-1-only baseline,
   with the positive control still WARN. FL Standard, `claim.md` before numbers.
3. If the judge can't beat Stage-1-only on held-out either → this approach also fails, and
   that becomes its own null_result. No result is assumed.

## Rejected alternatives

- **Trained ML model:** breaks the stdlib-only-hooks invariant (`requirements.txt` top),
  and 33 hand-authored examples cannot train or validate a model to any confidence — it
  would overfit exactly like the regex did.
- **Judge on EVERY response:** latency + cost + attack surface on every tool call, for no
  gain over judging only the ambiguous subset Stage 1 already narrows.
- **Cloud LLM judge:** sends untrusted fetched content off-perimeter — violates the
  Ollama-local PII posture. Local only.

## Salvageable direction (RFC-003 candidate — the auditor-endorsed path, NOT built yet)

The red-team's constructive half: **never let anything remove a warning; reduce noise
deterministically instead.**

1. **Display-context downgrade, never suppression.** If a descriptive-ambiguous hit sits
   inside a fenced code block, blockquote, or an explicit citation span, downgrade its
   SEVERITY (🚨 high → ⚠️ low / informational) — but keep it VISIBLE. Never warn→silent.
   This is regex/structural, adds no model, and cannot create a false-negative because the
   warning still fires.
2. **Audit every downgrade.** Any severity reduction writes to a persistent log so a
   suppressed-into-quiet injection is post-hoc discoverable (`hook_triggers.jsonl`).
3. **Accept the prose-FP as the SAFE failure.** The original annoyance — over-warning on
   security-research *prose* (not fenced) — is not safely fixable by any suppressor
   (that was CRITICAL-1/3). The honest conclusion: over-warning is the safe direction;
   make the warning less intrusive (lower severity, one-line) rather than removing it.

Known limit: display-context downgrade only helps fenced/quoted attack examples, not body
prose — so it is a PARTIAL, SAFE FP reduction, not a full one. That is the correct trade
for a warn-only control: buy less annoyance without buying a single false-negative.

This is a smaller, model-free change but still touches security hooks, so it gets its own
RFC-003 + FL run — not bolted on here at the tail of a long session. Left as the scoped,
red-team-informed next step for the owner.
