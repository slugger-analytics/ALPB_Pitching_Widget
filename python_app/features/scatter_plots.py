"""
Pitch movement scatter plots.

Layout: two side-by-side scatter plots (break-vs-velocity, vert-vs-horz break).
Callback: re-renders when pitch data, break type, or tagging method changes.
"""

import plotly.graph_objects as go
import pandas as pd

from dash import dcc, callback, Input, Output

from python_app.config import PITCH_COLORS, AXIS_LABELS
from python_app.lib.styles import info_card


# ── Layout ───────────────────────────────────────────────────────────────────

def layout_vel():
    return info_card(
        "Vertical Break vs Velocity",
        dcc.Graph(id="vel-plot"),
    )


def layout_break():
    return info_card(
        "Induced Vertical Break vs Horizontal Break",
        dcc.Graph(id="break-plot"),
    )


# ── Chart builder ────────────────────────────────────────────────────────────

def build_scatter(df, x_axis, y_axis, tag):
    """Build a Plotly scatter plot of pitch data."""
    if df is None or df.empty or x_axis not in df.columns or y_axis not in df.columns:
        return go.Figure()

    plot_df = df.copy()
    if tag in plot_df.columns:
        plot_df["_tag"] = plot_df[tag].apply(
            lambda v: "Untagged" if pd.isna(v) or v == "Undefined" else str(v)
        )
    else:
        plot_df["_tag"] = "Untagged"

    fig = go.Figure()
    for ptype in sorted(plot_df["_tag"].unique()):
        subset = plot_df[plot_df["_tag"] == ptype]
        fig.add_trace(go.Scatter(
            x=pd.to_numeric(subset[x_axis], errors="coerce"),
            y=pd.to_numeric(subset[y_axis], errors="coerce"),
            mode="markers",
            name=ptype,
            marker=dict(color=PITCH_COLORS.get(ptype, "gray"), size=6, opacity=0.7),
        ))

    fig.update_layout(
        xaxis_title=AXIS_LABELS.get(x_axis, x_axis),
        yaxis_title=AXIS_LABELS.get(y_axis, y_axis),
        template="plotly_white",
        legend_title="Pitch Type",
        margin=dict(l=50, r=20, t=30, b=50),
        height=300,
    )
    return fig


# ── Callbacks ────────────────────────────────────────────────────────────────

@callback(
    Output("vel-plot", "figure"),
    Input("pitch-data-store", "data"),
    Input("break-type", "value"),
    Input("tag-choice", "value"),
)
def update_vel_plot(pitch_records, break_type, tag):
    if not pitch_records:
        return {}
    return build_scatter(pd.DataFrame(pitch_records), "rel_speed", break_type, tag)


@callback(
    Output("break-plot", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_break_plot(pitch_records, tag):
    if not pitch_records:
        return {}
    return build_scatter(pd.DataFrame(pitch_records), "horz_break", "induced_vert_break", tag)
