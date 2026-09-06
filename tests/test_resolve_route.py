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

    def test_genitive_plural_matches(self):
        assert _match_task_type("проверка гипотез", WORKFLOWS) == "scientific-hypothesis-single"

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
        assert "sci-evidence:falsification.five_worlds" in artifact["selected_capabilities"]
        assert artifact["required_verifier"] == "skeptic"


class TestResolveIntegrationMulti:
    def test_resolve_competing_hypotheses_keeps_richer_workflow(self):
        artifact = resolve("сравни конкурирующие гипотезы", None)
        assert artifact["task_type"] == "scientific-hypothesis"
        assert "claim-decomposer:claim.atoms" in artifact["selected_capabilities"]
        assert "hypothesis-arbiter:ranked_hypotheses" in artifact["selected_capabilities"]
        assert artifact["required_verifier"] == "skeptic"
