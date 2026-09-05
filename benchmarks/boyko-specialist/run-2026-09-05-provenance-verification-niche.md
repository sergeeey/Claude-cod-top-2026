# boyko-specialist — provenance-disjointness verification niche

**Date:** 2026-09-05
**Object:** does `/boyko-specialist` correctly localize a real, narrow niche
(not a broad field) with genuinely web-verified seminal work and a
currently-active author, for a real open question this session surfaced --
and does it honestly scope what the niche does NOT solve?

## Why this run exists, and a status note

Per the skill's own frontmatter, it had never had a full end-to-end run
through the actual `Skill` tool before this ("experimental, частично
dogfooded... Полный end-to-end прогон через Skill(...) ещё не выполнялся").
This is that first full run. Real, current object: this session's own
`cross-domain` run found that a naive "second source" check regresses to the
same single-witness problem; skeptic's surviving reformulation called for
"provenance metadata disjointness, checked by code without write access to
the evidence field" -- without naming any established field for this.

## Protocol

Ran Phase 0 (Zero-Signal Gate -- concrete, passes), Phase 0.5 (Premise
Falsification Check -- premise held, no cheap local check overturned it),
Phase 1 (niche localization with real `WebSearch`, not from memory), Phase 2
(adopt the niche's vocabulary), Phase 3 (targeted search), Phase 4 (insider
methods, read-only), Phase 5 (verdict). Phase 6 (execution) not invoked --
no explicit "go" was given for that.

## Result

**Niche localized:** software supply-chain provenance attestation (SLSA /
in-toto), not "security" broadly. Niche confidence: **High**.

**Verification Gate honored -- real search, not assumed:**
- [VERIFIED] SLSA (Supply-chain Levels for Software Artifacts): maintained
  by OpenSSF, originated from Google's internal "Binary Authorization for
  Borg," real production framework (https://slsa.dev/).
- [VERIFIED] in-toto: Torres-Arias, Afzali, Kuppusamy, Curtmola, Cappos,
  "in-toto: Providing farm-to-table guarantees for bits and bytes," USENIX
  Security 2019. Torres-Arias confirmed currently active (Assistant
  Professor, Purdue ECE, per the university's own faculty page) -- recency
  requirement satisfied, not just a historical citation.

**Key mechanistic finding:** SLSA Level 2+ requires the provenance
attestation to be **signed by the hosted build platform, not the developer
submitting the artifact** -- this is a real, named, production-proven
instance of exactly the mechanism skeptic independently proposed in this
same session's `cross-domain` handoff ("checked by a hook without write
access to maturity_evidence"), arrived at from a completely different
direction (a specialist search, not a cross-domain analogy).

**Honest scoping in the verdict (Phase 5):** SLSA/in-toto solves the
mechanical half of the problem (who/when/how an artifact was produced,
tamper-evidently) -- it does NOT solve the semantic half (is the artifact's
CONTENT truthful). Explicitly named as a different, unsearched niche (closer
to peer review or forensic linguistics), not glossed over or claimed as
solved.

## Result vs the object question

Yes: the niche is genuinely narrow (not "security" or "software engineering"
broadly), both the framework and the author are real and web-verified with
recency confirmed, and the verdict is honest about a real limit (mechanism
!= truthfulness) rather than overclaiming full resolution.

## Limitation

Single search pass, Phase 3's "5-10 standard references" target was not
fully populated (2 sources found and verified: SLSA + the in-toto paper) --
a deeper run would search for 3-5 more standard references before Phase 4.
No specialist_score ranking was needed since only one clearly-dominant
candidate niche emerged, not 2+ competing verified candidates.
