"""
Shared, pure DataFrame filters for pitch-level records.

Kept dependency-free (no Dash / no I/O) so the same logic drives the web
callbacks and the PDF export identically.
"""

from __future__ import annotations

import pandas as pd

from python_app.config import BATTER_SIDE_ALL


def filter_batter_side(
    df: pd.DataFrame | None,
    side: str | None,
) -> pd.DataFrame | None:
    """Return the pitch rows faced by one batter side.

    Parameters
    ----------
    df : DataFrame or None
        Pitch-level records. Returned unchanged when ``None`` or empty.
    side : str or None
        ``None`` / ``""`` / ``"All"`` pass the frame through unchanged (rows with
        a null ``batter_side`` are kept). A concrete side (``"Right"`` / ``"Left"``)
        selects only matching rows, dropping nulls. If ``batter_side`` is missing
        for a concrete side, an empty same-columns slice is returned rather than
        raising ``KeyError``.

    Returns
    -------
    DataFrame or None
        The filtered frame (or the untouched input for the pass-through cases).
    """
    if df is None or df.empty:
        return df
    if side is None or side == "" or side == BATTER_SIDE_ALL:
        return df
    if "batter_side" not in df.columns:
        return df.iloc[0:0]
    return df[df["batter_side"] == side]


# The ALPB feed carries two different "we don't know" values in the pitch-type
# columns: a real null, and the literal STRING "NaN". `dropna()` removes only the
# first, and the string then survives an `!= "Undefined"` test, so a pitch type
# named "NaN" was printed with real usage percentages into the PITCH USAGE BY
# COUNT table of scouting reports handed to staff — measured on 10 of the 16
# pages of a live Charleston team PDF, e.g. Lance Lusk with 12 such pitches.
# Compared case-insensitively because the feed is not consistent about it.
UNKNOWN_PITCH_TYPES = {"undefined", "nan", "none", "null", ""}


def is_known_pitch_type(value) -> bool:
    """True when *value* names an actual pitch rather than a placeholder."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().casefold() not in UNKNOWN_PITCH_TYPES


def drop_unknown_pitch_types(
    df: pd.DataFrame | None,
    tag: str,
) -> pd.DataFrame | None:
    """Drop rows whose ``tag`` column holds no real pitch type.

    One helper for every caller — the web callbacks, the scatter plots, the heat
    maps and the PDF export each used to spell this filter out, and they had
    already drifted apart on which placeholders they caught.
    """
    if df is None or df.empty:
        return df
    if tag not in df.columns:
        return df
    return df[df[tag].map(is_known_pitch_type)]


def known_pitch_types(df: pd.DataFrame | None, tag: str) -> list[str]:
    """Sorted list of the real pitch types present in ``df[tag]``."""
    if df is None or df.empty or tag not in df.columns:
        return []
    return sorted({str(v) for v in df[tag].unique() if is_known_pitch_type(v)})
