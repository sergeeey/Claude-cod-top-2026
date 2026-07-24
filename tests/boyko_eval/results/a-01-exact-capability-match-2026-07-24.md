# Result: a-01-exact-capability-match (2026-07-24, boyko-baseline-v1)

**Grader verdict:** FAIL, non-critical (`grader.grade()`: passed=False, critical_failure=False
-- `critical: false` in `cases.yaml`).

**Failure (after fixing the grader bug this run exposed -- see below):**
`expected route_status='SELECTED' on the 'Route status:' line, found '** **AMBIGUOUS --
BLOCKED-ON-INPUT' instead`.

**Scenario-design confound (the actual, honest reason for the mismatch, disclosed rather than
smoothed over):** the prompt gives a hypothesis-testing goal ("I have a hypothesis... and want
to systematically generate and kill competing explanations") but never states the hypothesis
itself or any flake evidence. Boyko correctly refused to fabricate a discriminating test against
an unstated hypothesis ("Generating 'competing explanations' against an unstated hypothesis
would be fabrication, not method") and escalated for four concrete inputs before route selection
could complete. This is arguably *more* correct than the scenario anticipated -- the
`cases.yaml` `expected.route_status: SELECTED` assumes the methodology gets picked and locked
in immediately, but the prompt itself is under-specified in a way that legitimately blocks that.
The manual_review question ("Does the route trace select hypothesis-arbiter... via Tier A
capability-exact match, not a weaker semantic guess?") is *partially* answered: Boyko does
correctly identify Tier B / the ACH-Strong-Inference methodology as the right fit and cites the
repo's own `ach_matrix.md` template as evidence -- but the route is left `AMBIGUOUS --
BLOCKED-ON-INPUT`, not `SELECTED`, because instantiating the actual discriminating test needs
inputs the prompt never supplied. This scenario does not cleanly validate "does Boyko reach
SELECTED via a Tier A match" as originally intended.

**A genuine grader gap this run exposed and fixed this session (tool-verified, not
hypothetical):** the `route_status` check originally did a whole-transcript substring search for
the expected keyword (`"SELECTED".upper() in transcript.upper()`) instead of checking the actual
`Route status:` line. In this transcript the real status line reads "AMBIGUOUS --
BLOCKED-ON-INPUT", but an unrelated later sentence -- "The methodology is **selected**; the
discriminating test cannot be instantiated..." -- contains the word "selected" and made the
original check pass anyway. A first fix (anchor to the same line as `Route status:`) was tried
and *still* passed incorrectly, because this transcript's template puts the status sentence and
the next, unrelated sentence on the same line, separated only by a period. The working fix
anchors to the first sentence after `Route status:` (stop at the first `.` or newline, whichever
comes first) -- verified against this exact transcript, plus a full `pytest`+`ruff` pass with no
regressions across the suite.

## Transcript

Grounded. No prior flake investigation exists in `null_results/` (checked -- no matches), so this is a fresh path with nothing to contradict. There are three repo copies on disk (`Claude-cod-top-2026-main`, `repo-clean-test`, `repo-fresh`); I'll assume the main working copy unless you say otherwise.

One hard blocker before I can route the discriminating step: **you told me you have a hypothesis, but not what it is** -- and gave no flake evidence. Generating "competing explanations" against an unstated hypothesis would be fabrication, not method. So the Brief below sets up the full machinery and pins down exactly the four inputs that unlock it.

## Boyko Agent Brief

**Session goal:** Systematically enumerate and eliminate competing root-cause explanations for intermittent test-suite flakiness, converging on the mechanism(s) that survive a discriminating test.

**Pipeline:** L0 classify (mandatory) -> ACH matrix / Strong Inference (competing hypotheses) -> cheapest differentiating test -> `verifier`/`skeptic` context-blind review -> `decision.md`

**Confidence:** MEDIUM-HIGH on the *methodology* fit (debugging-with-competing-explanations is a textbook match for ACH + Platt's Strong Inference, and the repo ships `experiments/_template/ach_matrix.md` for exactly this). LOW on *any specific candidate ranking* -- I have neither your hypothesis nor the flake data.

### Route trace
- **Task Contract:** required output = diagnosis (root cause); shape = debug/research with competing explanations; constraints = flake evidence not yet provided; risk floor = Yellow (diagnosis only, no prod change yet).
- **L0 gate (step 0, mandatory -- not a menu option):** "Why does the suite flake?" is a **Causal** question -- each candidate is a mechanism, and the discriminating tests are interventional ("remove suspected source X -> does the flake disappear?"). This is the correct frame; a Descriptive "how often does it flake" would not kill any candidate.
- **Winning tier:** B (trigger exact) -- "generate and kill competing explanations" maps directly to the ACH/Strong-Inference pattern and the FL Recomposition/competing-hypotheses machinery.
- **Excluded candidates:** single-hypothesis FL Micro (you explicitly want a *tournament*, not one claim); EstimandOps full causal DAG (overkill at the identification stage -- apply it only if a survivor needs a formal causal claim).
- **Route status:** **AMBIGUOUS -- BLOCKED-ON-INPUT.** The methodology is selected; the discriminating test cannot be instantiated without the flake signature.

### CTA Card
- **Goal / acceptor:** a ranked competing-hypotheses matrix where >=1 candidate is killed and <=2 survive with a named discriminating test each.
- **Done when:** `ach_matrix.md` filled (hypotheses x evidence), one interventional test run, `decision.md` records which mechanism(s) survived and why.
- **Scope limits:** diagnosis only -- no fixes, no disabling/quarantining tests, no CI config edits until a survivor is confirmed. Do not "fix" by adding a retry wrapper (that hides the mechanism).
- **Current evidence:** [VERIFIED] no prior flake entry in `null_results/INDEX.md`. Everything else about *your* flake is [UNKNOWN].
- **Candidate paths (domain baseline taxonomy -- a starting frame, NOT evidence about your suite):** (1) test-order/pollution -- shared mutable state between tests; (2) timing/race -- sleeps, threads, async, real clock; (3) nondeterministic data -- dict/set ordering, unseeded random, `datetime.now()`; (4) external dependency -- network, DB, filesystem, ports; (5) resource contention -- parallel workers colliding on temp files/DB/ports.
- **Prior support:** LOW/UNKNOWN per candidate -- cannot weight without your hypothesis + logs.
- **Main uncertainty:** which candidate your stated hypothesis is (so I know which one to attack hardest) and what the failure signature is.
- **Verification cost:** SMALL -- the core discriminator (below) is a few rerun loops, not heavy compute.
- **Failure cost:** MODERATE -- a mis-diagnosed flake "fixed" by a retry wrapper wastes future debugging and erodes suite trust.
- **Reversibility:** easy (read-only diagnosis).
- **Verifier:** `verifier` or `skeptic`, context-blind (given only the matrix + a raw rerun log, not my reasoning) -- never me.
- **Potential check:** rejected path = "just add `pytest-rerunfailures` and move on." Rejected because it treats the symptom, produces zero information about the mechanism, and your explicit goal is to *kill explanations*, not mute them.
- **Simplicity check:** the 80/20 path *is* simple -- one experiment (isolation-vs-suite rerun with randomized order) splits the 5-candidate space roughly in half before any deep code reading. The harder path (per-candidate instrumentation) is only justified for whichever half survives.
- **Decision:** **Escalate for input** -- I need four things before the discriminating test is eligible.

### Discriminating test (the 80/20 splitter -- instantiate once you give me the flake ID)
- **Test:** take the flaking test(s) and run each (a) in isolation, N~50 reps, and (b) inside the full suite with **randomized order** (e.g. `pytest-randomly`), N~50 reps, fixed vs varied seed.
- **Outcome map:**
  - isolation-stable **+** suite-flaky -> kills "intrinsic" candidates (2,3 partial); **strengthens** order/pollution (1) and resource contention (5).
  - flaky even in isolation, varies with seed -> **strengthens** nondeterministic data (3); kills pollution (1).
  - flaky in isolation, seed-independent, correlates with load/wall-clock -> **strengthens** timing/race (2) or external dep (4).
- **Discrimination:** HIGH (each outcome branch kills or reverses at least one candidate).
- **Substrate:** PARTIAL -- READY only once I know the framework and can confirm a rerun/randomizer plugin exists (Substrate Gate 2a: "test couldn't run" != "hypothesis failed").
- **Cost:** SMALL.
- **Kill criterion:** if a candidate's predicted rerun pattern does not appear across 50 reps, it is killed and moved out of the live set (recorded, not deleted).

### Priorities
1. **Give me the four inputs** (below) -- impact 10/10, effort 1/10. Nothing downstream is eligible without them.
2. **Run the isolation-vs-suite rerun splitter** once inputs land -- impact 8/10, effort 3/10.
3. **Delegate `explorer`** to map the test framework + any existing retry/randomization/CI-retry config (so the Substrate Gate resolves to READY) -- impact 5/10, effort 2/10. Not started; I'll launch it once you confirm the working repo copy.

### The four inputs I need (this is the whole blocker)
1. **Your hypothesis** -- the specific mechanism you already suspect (so I attack *it* adversarially, not a strawman).
2. **Which test(s) flake** + the failure signature (assertion diff? timeout? exception + traceback tail?).
3. **When it flakes** -- CI only or local too? parallel (`-n`) or serial? tied to a particular order or machine?
4. **Framework + existing flake handling** -- pytest/unittest/jest/etc., and whether any rerun/randomize/CI-retry is already configured.

### Adjacent opportunities
1. Once a mechanism is confirmed, add a **regression guard** (e.g. `pytest-randomly` in CI to make order-dependence fail loudly) -- Impact 6, Evidence MEDIUM, Cost SMALL, Reversibility easy, Why now: cheapest way to stop the same class recurring silently.

### Evidence status
- [VERIFIED] No prior flakiness investigation in `null_results/INDEX.md` (grep, no matches).
- [VERIFIED] Repo ships `experiments/_template/ach_matrix.md` for competing-hypotheses analysis (referenced in `falsification-ladder.md`).
- [INFERRED] "Why flake" is a causal-identification task -> Strong Inference / ACH is the correct methodology.
- [UNKNOWN] Your actual hypothesis, the flaking test IDs, failure signatures, framework, and flake conditions -- all verification-required before the discriminating test is eligible.

### Learning Proposal
`none` yet -- a null_result or pattern entry becomes justified only after the tournament kills a candidate with evidence.

Send me the four inputs and I'll instantiate the ACH matrix with your hypothesis as a first-class competitor (not a privileged one -- it gets attacked like every other), then hand the survivors to a context-blind `verifier`.

TIP: When you list your flaking test(s), grab the **full traceback tail**, not just the last assertion line -- for flaky tests the frame *above* the failure (a `sleep`, a shared fixture, an unseeded `random`/`datetime.now()`) is usually where the mechanism lives, and it's exactly the evidence that lets me kill candidates 2 vs 3.

UROK: `pytest-randomly` seeds and shuffles test order *and* re-seeds `random`/`numpy`/`faker` before each test -- one plugin discriminates between "test-order pollution" and "unseeded-randomness" flakes at once, because it varies both axes independently. It prints the seed on failure so a flake becomes a one-command reproduction (`-p randomly --randomly-seed=<n>`).
