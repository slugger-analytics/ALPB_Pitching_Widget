"""Tests for the shared batter-side filter (:mod:`python_app.lib.filters`).

``filter_batter_side`` is a pure DataFrame helper:

* ``None`` / ``""`` / ``"All"``  → pass the frame through unchanged (nulls kept)
* a concrete side (``"Right"`` / ``"Left"``) → rows matching that side (NaN dropped)
* a missing ``batter_side`` column with a concrete side → empty same-columns frame
* ``None`` / empty frame → returned unchanged, never raising
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from python_app.lib.filters import filter_batter_side


@pytest.fixture
def df() -> pd.DataFrame:
    """Five pitches: Right, Left, Right, None, NaN batter sides."""
    return pd.DataFrame(
        {
            "batter_side": ["Right", "Left", "Right", None, np.nan],
            "rel_speed": [90.0, 88.0, 91.0, 89.0, 92.0],
        }
    )


@pytest.mark.parametrize("side", ["All", None, ""])
def test_pass_through_keeps_all_rows_including_nulls(df: pd.DataFrame, side) -> None:
    result = filter_batter_side(df, side)
    assert len(result) == 5
    assert result["batter_side"].isna().sum() == 2


def test_right_returns_two_rows(df: pd.DataFrame) -> None:
    result = filter_batter_side(df, "Right")
    assert len(result) == 2
    assert set(result["batter_side"]) == {"Right"}


def test_left_returns_one_row(df: pd.DataFrame) -> None:
    result = filter_batter_side(df, "Left")
    assert len(result) == 1
    assert set(result["batter_side"]) == {"Left"}


def test_concrete_side_excludes_nulls(df: pd.DataFrame) -> None:
    for side in ("Right", "Left"):
        result = filter_batter_side(df, side)
        assert result["batter_side"].isna().sum() == 0


def test_missing_column_concrete_side_returns_empty_same_columns(df: pd.DataFrame) -> None:
    no_side = df.drop(columns=["batter_side"])
    result = filter_batter_side(no_side, "Right")
    assert len(result) == 0
    assert list(result.columns) == list(no_side.columns)


def test_empty_df_no_raise() -> None:
    empty = pd.DataFrame(columns=["batter_side", "rel_speed"])
    result = filter_batter_side(empty, "Right")
    assert len(result) == 0


def test_none_df_no_raise() -> None:
    assert filter_batter_side(None, "Right") is None


def test_input_not_mutated(df: pd.DataFrame) -> None:
    before = df.copy(deep=True)
    filter_batter_side(df, "Right")
    pd.testing.assert_frame_equal(df, before)
