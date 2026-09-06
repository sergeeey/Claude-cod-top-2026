"""Tests for scripts/resolve_route.py -- had zero test coverage before this
file (found during a live audit, 2026-09-05, of why "надо проверить научную
гипотезу" failed to route while "гипотеза" alone succeeded)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from resolve_route import _match_task_type, load_workflows, resolve

WORKFLOWS = load_workflows()


class TestMatchTaskTypeRussianStem:
    # WHY this class exists: "гипотеза" (nominative singular) was the one
    # entry in the signal list left as a full word form while every English
    # entry nearby is already stemmed ("correlat", "falsif"). Russian case
    # endings mean the nominative form is not a substring of other cases.
    def test_nominative_matches(self):
        assert _match_task_type("это гипотеза", WORKFLOWS) == "scientific-hypothesis"

    def test_accusative_matches(self):
        """Regression: 'гипотезу' (accusative) previously did not match
        because the signal list held only the nominative 'гипотеза'."""
        assert (
            _match_task_type("надо проверить научную гипотезу", WORKFLOWS)
            == "scientific-hypothesis"
        )

    def test_genitive_plural_matches(self):
        assert _match_task_type("проверка гипотез", WORKFLOWS) == "scientific-hypothesis"

    def test_prepositional_matches(self):
        assert _match_task_type("подумай о гипотезе", WORKFLOWS) == "scientific-hypothesis"

    def test_instrumental_matches(self):
        assert _match_task_type("работаю с гипотезой", WORKFLOWS) == "scientific-hypothesis"


class TestMatchTaskTypeEnglish:
    def test_hypothesis_word(self):
        assert _match_task_type("test this hypothesis", WORKFLOWS) == "scientific-hypothesis"

    def test_stemmed_correlat(self):
        assert _match_task_type("does X correlate with Y", WORKFLOWS) == "scientific-hypothesis"

    def test_stemmed_falsif(self):
        assert _match_task_type("how would we falsify this", WORKFLOWS) == "scientific-hypothesis"


class TestMatchTaskTypeNoMatch:
    def test_unrelated_goal_returns_none(self):
        assert _match_task_type("fix the button color on the login page", WORKFLOWS) is None

    def test_empty_goal_returns_none(self):
        assert _match_task_type("", WORKFLOWS) is None


class TestResolveIntegration:
    def test_resolve_the_exact_audited_phrase(self):
        """The exact phrase from the 2026-09-05 audit that raised
        'no canonical workflow matches goal' before this fix."""
        artifact = resolve("надо проверить научную гипотезу", None)
        assert artifact["task_type"] == "scientific-hypothesis"
        assert "claim-decomposer:claim.atoms" in artifact["selected_capabilities"]
        assert artifact["required_verifier"] == "skeptic"
