"""
Pitch-type usage by ball–strike count.

Layout   : single card with a pivot table.
Callback : re-renders when pitch data or tagging method changes.
Builder  : ``compute_pitch_split`` is the single source of truth — also called
           by ``pdf_export`` for the PDF report.
"""

from __future__ import annotations

import pandas as pd

from dash import Input, Output, callback, html

from python_app.lib.styles import info_card, styled_table


# ═══════════════════════════════════════════════════════════════════════════════
#  Layout
# ═══════════════════════════════════════════════════════════════════════════════

def layout():
    """Card wrapping the pitch-split table."""
    return info_card(
        "Pitch Type Percentages for Each Count",
        html.Div(id="pitch-table-container"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Public analysis helper
# ═══════════════════════════════════════════════════════════════════════════════

def compute_pitch_split(pitch_data: pd.DataFrame, tag: str) -> pd.DataFrame:
    """Calculate the percentage of each pitch type thrown per ball–strike count.

    Parameters
    ----------
    pitch_data : DataFrame
        Pitch-level records (must contain ``balls``, ``strikes``, and *tag*).
    tag : str
        Column used for pitch-type grouping.

    Returns
    -------
    DataFrame
        Pivoted table with one row per count and one column per pitch type.
    """
    empty = pd.DataFrame(columns=["Count"])

    if pitch_data is None or pitch_data.empty:
        return empty

    df = pitch_data.copy()
    df = df.dropna(subset=["balls", "strikes", tag])
    df = df[df[tag] != "Undefined"]
    if df.empty:
        return empty

    df["Count"] = df["balls"].astype(str) + " - " + df["strikes"].astype(str)

    grouped = df.groupby(["Count", tag]).size().reset_index(name="n")
    totals = grouped.groupby("Count")["n"].transform("sum")
    grouped["pct"] = (grouped["n"] / totals * 100).round(1)

    result = (
        grouped
        .pivot_table(index="Count", columns=tag, values="pct", fill_value=0)
        .reset_index()
        .sort_values("Count")
        .reset_index(drop=True)
    )
    result.columns.name = None
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Dash callback
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("pitch-table-container", "children"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_pitch_table(
    pitch_records: list[dict] | None,
    tag: str,
):
    if not pitch_records:
        return ""
    split_df = compute_pitch_split(pd.DataFrame(pitch_records), tag)
    if split_df.empty:
        return html.P("No pitch split data available.")
    return styled_table(split_df, page_size=12)
