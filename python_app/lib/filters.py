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
