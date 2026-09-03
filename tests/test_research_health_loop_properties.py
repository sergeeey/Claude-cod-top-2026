r"""Property-based (hypothesis) tests for research_health_loop.py's
escape-aware pipe-table parser.

WHY: `_split_row_escape_aware` was itself the subject of a real, live-only
bug found and backported on 2026-09-01 (PR #303) -- the OLD naive
`line.strip("|").split("|")` mis-parsed 26/193 real pearl_registry rows
(13%) containing inline math with escaped pipes like `\|G-1\|`, and the
hand-written regression tests added in that PR only cover the specific
shapes someone thought to write by hand. This file generalizes that
coverage: property-based generation explores cell-content shapes no one
enumerated by hand, checking the same escape-parity invariant the function
itself documents.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
import research_health_loop as rhl

# Cell text with no pipe or backslash at all -- safe to place between
# delimiters without creating an accidental escape or an extra column.
_PLAIN_CELL = st.text(
    alphabet=st.characters(blacklist_characters="|\\\n"),
    max_size=20,
).map(str.strip)

_ARBITRARY_TEXT = st.text(max_size=200)


class TestCrashSafety:
    @given(text=_ARBITRARY_TEXT)
    @settings(max_examples=300)
    def test_never_raises(self, text: str) -> None:
        result = rhl._split_row_escape_aware(text)
        assert result is None or isinstance(result, list)

    @given(text=_ARBITRARY_TEXT)
    @settings(max_examples=300)
    def test_no_pipe_at_all_returns_none(self, text: str) -> None:
        if "|" in text:
            return
        assert rhl._split_row_escape_aware(text) is None


class TestCellRoundTrip:
    """Regression class generalized: joining N plain (no pipe/backslash)
    cells with unescaped '|' delimiters, wrapped in outer pipes (the real
    markdown-table-row shape), must recover exactly those N cells."""

    @given(cells=st.lists(_PLAIN_CELL, min_size=1, max_size=8))
    @settings(max_examples=300)
    def test_plain_cells_recovered_exactly(self, cells: list[str]) -> None:
        row = "| " + " | ".join(cells) + " |"
        result = rhl._split_row_escape_aware(row)
        assert result == cells

    @given(cells=st.lists(_PLAIN_CELL, min_size=1, max_size=8))
    @settings(max_examples=300)
    def test_escaped_pipe_inside_a_cell_stays_in_that_cell(self, cells: list[str]) -> None:
        """Regression generalization of the actual 2026-08-21 bug: inject a
        literal escaped pipe into the middle cell (when there is one) and
        confirm it survives as content, un-escaped, without creating an
        extra column or bleeding into a neighboring cell."""
        if len(cells) < 2:
            return
        mid = len(cells) // 2
        cells_with_math = list(cells)
        cells_with_math[mid] = cells[mid] + r"\|bound\|"
        row = "| " + " | ".join(cells_with_math) + " |"
        result = rhl._split_row_escape_aware(row)
        assert result is not None
        assert len(result) == len(cells)
        assert result[mid] == cells[mid] + "|bound|"
