"""
Pitch-movement scatter plots.

Layout   : two side-by-side cards (velocity vs break, vert-break vs horz-break).
Callback : re-renders when pitch data, break type, or tagging method changes.
Builder  : ``build_scatter`` is the single source of truth — also called by
           ``pdf_export`` for the PDF report.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dash import Input, Output, callback, dcc

from python_app.config import AXIS_LABELS, PITCH_COLORS
from python_app.lib.styles import info_card


# ═══════════════════════════════════════════════════════════════════════════════
#  Layout fragments (consumed by app.py)
# ═══════════════════════════════════════════════════════════════════════════════

def layout_vel() -> info_card:
    """Card wrapping the velocity scatter plot."""
    return info_card(
        "Vertical/Horizontal Break vs Velocity",
        dcc.Graph(id="vel-plot", config={"responsive": True}, style={"width": "100%"}),
    )


def layout_break() -> info_card:
    """Card wrapping the break scatter plot."""
    return info_card(
        "Induced Vertical Break vs Horizontal Break",
        dcc.Graph(id="break-plot", config={"responsive": True}, style={"width": "100%"}),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Public chart builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_scatter(
    df: pd.DataFrame,
    x_axis: str,
    y_axis: str,
    tag: str,
) -> go.Figure:
    """Build a colour-coded Plotly scatter of pitch data.

    Parameters
    ----------
    df : DataFrame
        Pitch-level records (must contain *x_axis*, *y_axis*, and *tag* columns).
    x_axis, y_axis : str
        Column names mapped to the X / Y axes.
    tag : str
        Column used for pitch-type colouring (e.g. ``"auto_pitch_type"``).

    Returns
    -------
    go.Figure
        Ready-to-display Plotly figure (empty if input is invalid).
    """
    if df is None or df.empty or x_axis not in df.columns or y_axis not in df.columns:
        return go.Figure()

    plot_df = df.copy()
    if tag in plot_df.columns:
        plot_df = plot_df[
            plot_df[tag].notna() & (plot_df[tag] != "Undefined")
        ]
        plot_df["_tag"] = plot_df[tag].astype(str)
    else:
        return go.Figure()

    if plot_df.empty:
        return go.Figure()

    fig = go.Figure()
    for ptype in sorted(plot_df["_tag"].unique()):
        subset = plot_df[plot_df["_tag"] == ptype]
        fig.add_trace(go.Scatter(
            x=pd.to_numeric(subset[x_axis], errors="coerce"),
            y=pd.to_numeric(subset[y_axis], errors="coerce"),
            mode="markers",
            name=ptype,
            marker=dict(
                color=PITCH_COLORS.get(ptype, "gray"),
                size=6,
                opacity=0.7,
            ),
        ))

    fig.update_layout(
        xaxis_title=AXIS_LABELS.get(x_axis, x_axis),
        yaxis_title=AXIS_LABELS.get(y_axis, y_axis),
        template="plotly_white",
        legend_title="Pitch Type",
        legend=dict(orientation="h", yanchor="top", y=-0.25),
        margin=dict(l=50, r=20, t=30, b=50),
        height=300,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  Dash callbacks
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("vel-plot", "figure"),
    Input("pitch-data-store", "data"),
    Input("break-type", "value"),
    Input("tag-choice", "value"),
)
def update_vel_plot(
    pitch_records: list[dict] | None,
    break_type: str,
    tag: str,
) -> go.Figure:
    if not pitch_records:
        return go.Figure()
    return build_scatter(pd.DataFrame(pitch_records), "rel_speed", break_type, tag)


@callback(
    Output("break-plot", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_break_plot(
    pitch_records: list[dict] | None,
    tag: str,
) -> go.Figure:
    if not pitch_records:
        return go.Figure()
    return build_scatter(
        pd.DataFrame(pitch_records), "horz_break", "induced_vert_break", tag,
    )
