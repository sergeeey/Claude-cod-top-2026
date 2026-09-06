"""Tests for scripts/resolve_route.py -- had zero test coverage before
2026-09-05's audit found "надо проверить научную гипотезу" failed to route
while "гипотеза" alone succeeded.

2026-09-06 update: a second audit found the single canonical workflow always
ran claim-decomposer (whose own SKILL.md says "НЕ для: целостный анализ
одной простой гипотезы") and sci-hypothesis (a GENERATOR, not a tester) for
EVERY hypothesis, simple or competing. A default single-hypothesis mention
now routes to the new, faster scientific-hypothesis-single workflow;
explicit plurality/competition signals still route to the original,
richer scientific-hypothesis workflow -- mirroring
boyko-scientific-consortium's own already-validated branch rule.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from resolve_route import _match_task_type, load_workflows, resolve

WORKFLOWS = load_workflows()


class TestMatchTaskTypeRussianStemDefaultsToSingle:
    # WHY this class exists: "гипотеза" (nominative singular) was the one
    # entry in the signal list left as a full word form while every English
    # entry nearby is already stemmed ("correlat", "falsif"). Russian case
    # endings mean the nominative form is not a substring of other cases.
    # A plain mention with no plurality/competition signal now defaults to
    # the single-hypothesis fast path (see TestMultiHypothesisRoutesToRicherWorkflow).
    def test_nominative_matches(self):
        assert _match_task_type("это гипотеза", WORKFLOWS) == "scientific-hypothesis-single"

    def test_accusative_matches(self):
        """Regression: 'гипотезу' (accusative) previously did not match at
        all because the signal list held only the nominative 'гипотеза'."""
        assert (
            _match_task_type("надо проверить научную гипотезу", WORKFLOWS)
            == "scientific-hypothesis-single"
        )

    def test_dative_matches(self):
        """WHY not 'проверка гипотез' here (Codex review, PR #375): that
        phrase is genitive PLURAL ('of the hypotheses') and correctly routes
        to the richer workflow now -- see
        TestMultiHypothesisRoutesToRicherWorkflow::test_russian_bare_genitive_plural_is_multi.
        Dative singular ('гипотезам' would be plural too, so using the
        singular 'гипотезе'-adjacent dative-like phrasing here) keeps this
        class's coverage of unambiguously-singular case forms intact."""
        assert (
            _match_task_type("дай оценку этой гипотезе", WORKFLOWS)
            == "scientific-hypothesis-single"
        )

    def test_prepositional_matches(self):
        assert _match_task_type("подумай о гипотезе", WORKFLOWS) == "scientific-hypothesis-single"

    def test_instrumental_matches(self):
        assert _match_task_type("работаю с гипотезой", WORKFLOWS) == "scientific-hypothesis-single"

    def test_causal_hypothesis_no_plurality_signal_is_still_single(self):
        """Regression (2026-09-06 audit): a causal hypothesis is not
        automatically a MULTI-hypothesis one -- 'причинную' alone must not
        trigger the richer workflow."""
        assert (
            _match_task_type("исследуй причинную гипотезу", WORKFLOWS)
            == "scientific-hypothesis-single"
        )


class TestMatchTaskTypeEnglishDefaultsToSingle:
    def test_hypothesis_word(self):
        assert _match_task_type("test this hypothesis", WORKFLOWS) == "scientific-hypothesis-single"

    def test_stemmed_correlat(self):
        assert (
            _match_task_type("does X correlate with Y", WORKFLOWS) == "scientific-hypothesis-single"
        )

    def test_stemmed_falsif(self):
        assert (
            _match_task_type("how would we falsify this", WORKFLOWS)
            == "scientific-hypothesis-single"
        )


class TestMultiHypothesisRoutesToRicherWorkflow:
    # WHY this class exists: boyko-scientific-consortium/SKILL.md already
    # documents "≥2 конкурирующих механизма -> hypothesis-arbiter" as the
    # exception requiring an explicit signal -- these are that signal.
    def test_russian_competing_signal(self):
        assert (
            _match_task_type("сравни конкурирующие гипотезы", WORKFLOWS) == "scientific-hypothesis"
        )

    def test_english_competing_signal(self):
        assert (
            _match_task_type("compare competing hypotheses", WORKFLOWS) == "scientific-hypothesis"
        )

    def test_english_plural_hypotheses_alone_is_multi(self):
        """Regression: 'hypothesis' (full singular) does not match
        'hypotheses' (plural) as a substring -- they diverge in the last two
        letters. Needed the same stem fix as the Russian case-ending bug,
        just in English."""
        assert _match_task_type("here are several hypotheses", WORKFLOWS) == "scientific-hypothesis"

    def test_english_several_signal(self):
        assert (
            _match_task_type("several hypotheses to consider", WORKFLOWS) == "scientific-hypothesis"
        )

    def test_bare_plural_hypotheses_is_multi(self):
        """Codex review, PR #375: 'test two hypotheses' / 'test hypotheses A
        and B' contain no phrase from the narrower signal list, only the
        bare plural word -- must still route to the richer workflow."""
        assert _match_task_type("test two hypotheses", WORKFLOWS) == "scientific-hypothesis"
        assert _match_task_type("test hypotheses A and B", WORKFLOWS) == "scientific-hypothesis"

    def test_russian_bare_genitive_plural_is_multi(self):
        """Codex review, PR #375: 'проверка гипотез' (genitive plural, 'OF
        the hypotheses') is inherently plural by its own grammatical form --
        it was wrongly falling through to the single-hypothesis default."""
        assert _match_task_type("проверка гипотез", WORKFLOWS) == "scientific-hypothesis"

    def test_russian_genitive_singular_is_still_single(self):
        """Sanity check for the regex precision: 'гипотезы' with a trailing
        letter (genitive SINGULAR, 'of the hypothesis') must NOT trigger the
        same rule as the bare plural stem 'гипотез'."""
        assert _match_task_type("проверка гипотезы", WORKFLOWS) == "scientific-hypothesis-single"


class TestGenerationIntentRoutesToRicherWorkflow:
    # WHY this class exists (Codex review, PR #375, 2026-09-06): the -single
    # workflow has no sci-hypothesis step -- it cannot GENERATE a hypothesis,
    # only falsify an existing one. A generation request has a hypothesis
    # signal but no plurality signal, so without this explicit check it
    # would incorrectly fall through to a workflow with nothing to generate.
    def test_russian_generation_signal(self):
        assert _match_task_type("сгенерируй гипотезу о X", WORKFLOWS) == "scientific-hypothesis"

    def test_english_generation_signal(self):
        assert (
            _match_task_type("generate a scientific hypothesis about X", WORKFLOWS)
            == "scientific-hypothesis"
        )


class TestMultiHypothesisSignalPrecision:
    # WHY this class exists (self-review, 2026-09-06): an earlier draft
    # included a bare "compet" fallback in _MULTI_HYPOTHESIS_SIGNALS, which
    # matched "test the hypothesis that market COMPETition reduces prices"
    # -- a SINGLE hypothesis whose subject happens to be economic
    # competition, wrongly routed by topic rather than by the hypothesis's
    # actual form. Caught before merge, not after.
    def test_competition_as_topic_is_not_multi_hypothesis(self):
        assert (
            _match_task_type(
                "test the hypothesis that market competition reduces prices", WORKFLOWS
            )
            == "scientific-hypothesis-single"
        )

    def test_competent_is_not_multi_hypothesis(self):
        assert (
            _match_task_type("is this hypothesis testable by a competent reviewer", WORKFLOWS)
            == "scientific-hypothesis-single"
        )


class TestWeakSignalPrecision:
    # WHY this class exists (audit, 2026-09-06, live-verified): "research", "experiment" and
    # "predict" were originally strong (standalone-triggering) signals, inherited from
    # estimand-ops.md's auto-trigger keyword list -- a list meant for a human already judging
    # relevance, not a blind substring matcher. All three are ordinary English words with wide
    # non-scientific-hypothesis usage. Verified live before this fix: all three phrases below
    # matched scientific-hypothesis-single despite none of them being a scientific hypothesis
    # task.
    def test_bare_research_does_not_match(self):
        assert _match_task_type("research Python packaging tools", WORKFLOWS) is None

    def test_bare_predict_does_not_match(self):
        assert _match_task_type("predict disk usage next week", WORKFLOWS) is None

    def test_bare_experiment_does_not_match(self):
        assert _match_task_type("run an experiment with button colors", WORKFLOWS) is None

    def test_two_weak_signals_together_still_match(self):
        # Weak signals co-occurring is still a real (if soft) hypothesis-adjacent signal --
        # only a LONE weak signal is the false-positive pattern this class guards against.
        assert (
            _match_task_type("design an experiment to predict the outcome", WORKFLOWS) is not None
        )

    def test_weak_signal_with_strong_signal_still_matches(self):
        assert (
            _match_task_type("run an experiment to test the hypothesis that X causes Y", WORKFLOWS)
            == "scientific-hypothesis-single"
        )


class TestMultiHypothesisStemCount:
    # WHY this class exists (audit, 2026-09-06, live-verified): "сравни гипотезу A с гипотезой
    # B" names two DIFFERENT hypotheses, but each individual mention is grammatically singular
    # (accusative "гипотезу", instrumental "гипотезой") -- neither matches the bare
    # genitive-plural regex nor any fixed _MULTI_HYPOTHESIS_SIGNALS phrase. The stem itself still
    # appears twice, once per hypothesis, regardless of declension.
    def test_two_declined_singular_mentions_route_to_multi(self):
        assert (
            _match_task_type("сравни гипотезу A с гипотезой B", WORKFLOWS)
            == "scientific-hypothesis"
        )

    def test_two_english_singular_mentions_route_to_multi(self):
        assert (
            _match_task_type("compare hypothesis A against hypothesis B", WORKFLOWS)
            == "scientific-hypothesis"
        )

    def test_single_mention_stays_single(self):
        assert (
            _match_task_type("сравни гипотезу A с реальностью", WORKFLOWS)
            == "scientific-hypothesis-single"
        )


class TestMatchTaskTypeNoMatch:
    def test_unrelated_goal_returns_none(self):
        assert _match_task_type("fix the button color on the login page", WORKFLOWS) is None

    def test_empty_goal_returns_none(self):
        assert _match_task_type("", WORKFLOWS) is None


class TestResolveIntegrationSingle:
    def test_resolve_the_exact_audited_phrase(self):
        """The exact phrase from the 2026-09-05 audit that raised
        'no canonical workflow matches goal' before the stem fix, and that
        the 2026-09-06 audit found always over-routed through
        claim-decomposer + sci-hypothesis before this workflow existed."""
        artifact = resolve("надо проверить научную гипотезу", None)
        assert artifact["task_type"] == "scientific-hypothesis-single"
        assert "claim-decomposer:claim.atoms" not in artifact["selected_capabilities"]
        assert "sci-hypothesis:hypothesis.candidates" not in artifact["selected_capabilities"]
        # WHY this assertion (audit, 2026-09-06, live-verified): estimand-bridge's own SKILL.md
        # hard-STOPs when no experiments/<id>/estimand.md exists on disk yet -- exactly the case
        # for a fresh ad-hoc hypothesis like this one. Keeping it as a step here would make the
        # "fast path" fail on its very first real invocation. sci-evidence's own Step 0 already
        # runs the EstimandOps L0 gate this fast path needs.
        assert "estimand-bridge:estimand.criteria" not in artifact["selected_capabilities"]
        assert "sci-evidence:falsification.five_worlds" in artifact["selected_capabilities"]
        assert artifact["required_verifier"] == "skeptic"


class TestResolveIntegrationMulti:
    def test_resolve_competing_hypotheses_keeps_richer_workflow(self):
        artifact = resolve("сравни конкурирующие гипотезы", None)
        assert artifact["task_type"] == "scientific-hypothesis"
        assert "claim-decomposer:claim.atoms" in artifact["selected_capabilities"]
        assert "hypothesis-arbiter:ranked_hypotheses" in artifact["selected_capabilities"]
        assert artifact["required_verifier"] == "skeptic"

    def test_estimand_l0_gate_runs_before_estimand_bridge(self):
        # WHY this test exists (audit, 2026-09-06, live-verified): a real multi-hypothesis
        # phrase, routed through this exact resolver to scientific-hypothesis.yaml, was
        # traced by hand into estimand-bridge's own Step 1 with no experiments/<id>/
        # estimand.md on disk -- confirming the hard-STOP risk already fixed once in
        # scientific-hypothesis-single.yaml (#376) also exists here. estimand-l0-gate was
        # added as a step BEFORE estimand-bridge (not a change to that shared skill) to
        # materialize a minimal estimand.md so the STOP condition never fires on a fresh
        # ad-hoc request.
        artifact = resolve("сравни конкурирующие гипотезы", None)
        caps = artifact["selected_capabilities"]
        assert "estimand-l0-gate:estimand.l0_materialized" in caps
        assert caps.index("estimand-l0-gate:estimand.l0_materialized") < caps.index(
            "estimand-bridge:estimand.criteria"
        )
        assert caps.index("estimand-l0-gate:estimand.l0_materialized") < caps.index(
            "claim-decomposer:claim.atoms"
        )


class TestRealHistoricalPhrases:
    # WHY this class exists (audit, 2026-09-06): every phrase below is quoted verbatim
    # from a real, pre-existing file in this repo -- an actual experiment claim, a real
    # commit subject, or a skill's own trigger phrase -- not invented to probe the
    # router. Crafted test phrases (the rest of this file) are still [VERIFIED-SYNTHETIC]
    # in this repo's own integrity.md terms; these are the [VERIFIED-REAL] counterpart.
    # No false positive was found on any of the 12 real phrases checked in this audit;
    # this class keeps the 5 most informative ones as a permanent regression guard.

    def test_real_causal_claim_from_hypothesis_arbiter_pilot_matches(self):
        # experiments/20260728-hypothesis-arbiter-taxonomy-pilot/claim.md
        assert (
            _match_task_type(
                "adding the 8-class generator taxonomy to hypothesis-arbiter's spawn "
                "step causes the candidate hypothesis table to include an "
                "artifact-class explanation",
                WORKFLOWS,
            )
            is not None
        )

    def test_real_falsified_claim_from_config_effectiveness_matches(self):
        # experiments/20260727-config-effectiveness-opportunistic/claim.md
        assert (
            _match_task_type(
                "across the opportunistically accumulated task population, the "
                "standard config's catch-rate exceeds vanilla's by >=20 percentage "
                "points. falsified if the accumulated risk difference stays below 0.2",
                WORKFLOWS,
            )
            == "scientific-hypothesis-single"
        )

    def test_real_sci_evidence_trigger_phrase_matches(self):
        # skills/extensions/sci-evidence/SKILL.md's own trigger list
        assert _match_task_type("сломай мою гипотезу", WORKFLOWS) == "scientific-hypothesis-single"

    def test_real_claim_decomposer_trigger_phrase_does_not_match(self):
        # skills/core/claim-decomposer/SKILL.md's own trigger list -- a real trigger
        # for a DIFFERENT skill, correctly not swept into scientific-hypothesis.
        assert _match_task_type("разложи утверждение", WORKFLOWS) is None

    def test_real_commit_subjects_do_not_match(self):
        # 5 real commit subjects from `git log origin/main`, chosen as ordinary dev
        # work with zero hypothesis-testing language -- a genuine precision check
        # (as opposed to a crafted counter-example) that no false positive slipped
        # through on real, unscripted text.
        real_commit_subjects = [
            "anchor locality_escalation_guard state to git root, not cwd",
            "fix hooks match suffixed Current Focus headers in knowledge_librarian.py",
            "surface xfailed xpassed in reliability_vector.py's security line",
            "remove dead unsafe send_webhook duplicate and md5 usedforsecurity",
            "use rglob for contradiction scan, fix stale docstring paths",
        ]
        for subject in real_commit_subjects:
            assert _match_task_type(subject, WORKFLOWS) is None, subject

    def test_real_evidence_chain_verifier_question_is_a_known_recall_gap(self):
        # experiments/20260906-evidence-chain-verifier/claim.md -- a genuine, real
        # research question from this repo's own history with NO signal words at
        # all ("does a specific mechanism distinguish X from Y"). Documented here
        # as a KNOWN, accepted scope boundary, not silently patched: adding a new
        # bare keyword to cover this one real phrase risks reopening exactly the
        # weak-signal false-positive problem this same audit just closed.
        assert (
            _match_task_type(
                "does a specific verification mechanism distinguish an honest run "
                "from 4 named categories of fabrication",
                WORKFLOWS,
            )
            is None
        )
