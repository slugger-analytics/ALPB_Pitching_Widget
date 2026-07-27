"""Tests for the pitch-usage table row-max highlight styling.

The row-max highlight must be visually unmistakable and identical between the
Dash web table and the matplotlib PDF export, so both pull the same colours
from :mod:`python_app.config`.
"""

from __future__ import annotations

import pandas as pd

from python_app.config import HIGHLIGHT_BG, HIGHLIGHT_TEXT
from python_app.lib.styles import _row_max_highlight_rules


def test_highlight_uses_config_colours() -> None:
    """Every emitted rule paints the shared navy background + white text."""
    df = pd.DataFrame({"Count": ["0 - 0"], "FB": [70.0], "SL": [30.0]})
    rules = _row_max_highlight_rules(df, start_col=1)

    assert rules, "expected a highlight rule for the row max"
    for rule in rules:
        assert rule["backgroundColor"] == HIGHLIGHT_BG
        assert rule["color"] == HIGHLIGHT_TEXT
        assert rule["fontWeight"] == "bold"


def test_highlight_targets_only_row_max() -> None:
    """Only the largest numeric cell in the row is highlighted."""
    df = pd.DataFrame({"Count": ["0 - 0"], "FB": [70.0], "SL": [30.0]})
    rules = _row_max_highlight_rules(df, start_col=1)

    highlighted = {(r["if"]["row_index"], r["if"]["column_id"]) for r in rules}
    assert highlighted == {(0, "FB")}


def test_highlight_ties_are_all_highlighted() -> None:
    """When two columns tie for the max, both are highlighted."""
    df = pd.DataFrame({"Count": ["0 - 0"], "FB": [50.0], "SL": [50.0]})
    rules = _row_max_highlight_rules(df, start_col=1)

    highlighted_cols = {r["if"]["column_id"] for r in rules}
    assert highlighted_cols == {"FB", "SL"}


def test_highlight_skips_non_numeric_rows() -> None:
    """A row with no numeric values yields no highlight rules."""
    df = pd.DataFrame({"Count": ["0 - 0"], "FB": ["-"], "SL": ["-"]})
    rules = _row_max_highlight_rules(df, start_col=1)

    assert rules == []


def test_highlight_is_per_row() -> None:
    """Each row gets its own max highlighted independently."""
    df = pd.DataFrame(
        {
            "Count": ["0 - 0", "1 - 0"],
            "FB": [70.0, 20.0],
            "SL": [30.0, 80.0],
        }
    )
    rules = _row_max_highlight_rules(df, start_col=1)

    highlighted = {(r["if"]["row_index"], r["if"]["column_id"]) for r in rules}
    assert highlighted == {(0, "FB"), (1, "SL")}
