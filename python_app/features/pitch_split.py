"""
Pitch type usage by ball-strike count.

Layout: table showing % of each pitch type for every count.
Callback: re-renders when pitch data or tagging method changes.
Analysis: computes the pivot table from raw pitch records.
"""

import pandas as pd

from dash import html, callback, Input, Output

from python_app.lib.styles import info_card, styled_table


# ── Layout ───────────────────────────────────────────────────────────────────

def layout():
    return info_card(
        "Pitch Type Percentages for Each Count",
        html.Div(id="pitch-table-container"),
    )


# ── Analysis ─────────────────────────────────────────────────────────────────

def compute_pitch_split(pitch_data, tag):
    """Calculate % of each pitch type thrown in every ball-strike count."""
    if pitch_data is None or pitch_data.empty:
        return pd.DataFrame(columns=["Count"])

    df = pitch_data.copy()
    df = df.dropna(subset=["balls", "strikes", tag])
    df = df[df[tag] != "Undefined"]
    if df.empty:
        return pd.DataFrame(columns=["Count"])

    df["Count"] = df["balls"].astype(str) + " - " + df["strikes"].astype(str)

    grouped = df.groupby(["Count", tag]).size().reset_index(name="n")
    totals = grouped.groupby("Count")["n"].transform("sum")
    grouped["pct"] = (grouped["n"] / totals * 100).round(1)

    result = grouped.pivot_table(
        index="Count", columns=tag, values="pct", fill_value=0,
    ).reset_index()
    result = result.sort_values("Count").reset_index(drop=True)
    result.columns.name = None
    return result


# ── Callback ─────────────────────────────────────────────────────────────────

@callback(
    Output("pitch-table-container", "children"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_pitch_table(pitch_records, tag):
    if not pitch_records:
        return ""
    split_df = compute_pitch_split(pd.DataFrame(pitch_records), tag)
    if split_df.empty:
        return html.P("No pitch split data available.")
    return styled_table(split_df, page_size=12)
