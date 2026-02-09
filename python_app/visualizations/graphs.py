"""
Scatter plot visualizations for pitch data.

Generates break-vs-velocity and break-vs-break scatter plots using Plotly.
Equivalent to getGraphs.R.
"""

import plotly.graph_objects as go
import pandas as pd
import numpy as np

# Axis label mappings
AXIS_LABELS = {
    "induced_vert_break": "Induced Vertical Break (inches)",
    "horz_break": "Horizontal Break (inches)",
    "rel_speed": "Velocity (mph)",
}

AXIS_SHORT_LABELS = {
    "induced_vert_break": "Induced Vertical Break",
    "horz_break": "Horizontal Break",
    "rel_speed": "Velocity",
}

# Pitch type color mapping (matches R version)
PITCH_COLORS = {
    "Fastball": "red",
    "Four-Seam": "red",
    "Changeup": "blue",
    "ChangeUp": "blue",
    "Sinker": "green",
    "Curveball": "brown",
    "Slider": "purple",
    "Splitter": "black",
    "Cutter": "pink",
    "Untagged": "gray",
}


def build_graph(df, x_axis, y_axis, tag):
    """
    Build a scatter plot of pitch data.

    Args:
        df: DataFrame with pitch data.
        x_axis: Column name for x-axis (rel_speed, induced_vert_break, horz_break).
        y_axis: Column name for y-axis.
        tag: Column name for pitch type tagging (auto_pitch_type or tagged_pitch_type).

    Returns:
        A Plotly Figure object.
    """
    if df is None or df.empty or x_axis not in df.columns or y_axis not in df.columns:
        return go.Figure()

    plot_df = df.copy()

    # Replace undefined/NaN tags with "Untagged"
    if tag in plot_df.columns:
        plot_df["TagStatus"] = plot_df[tag].apply(
            lambda v: "Untagged" if pd.isna(v) or v == "Undefined" else str(v)
        )
    else:
        plot_df["TagStatus"] = "Untagged"

    fig = go.Figure()

    for pitch_type in plot_df["TagStatus"].unique():
        subset = plot_df[plot_df["TagStatus"] == pitch_type]
        color = PITCH_COLORS.get(pitch_type, "gray")
        fig.add_trace(
            go.Scatter(
                x=pd.to_numeric(subset[x_axis], errors="coerce"),
                y=pd.to_numeric(subset[y_axis], errors="coerce"),
                mode="markers",
                name=pitch_type,
                marker=dict(color=color, size=6, opacity=0.7),
            )
        )

    fig.update_layout(
        xaxis_title=AXIS_LABELS.get(x_axis, x_axis),
        yaxis_title=AXIS_LABELS.get(y_axis, y_axis),
        template="plotly_white",
        legend_title="Pitch Tag",
        margin=dict(l=50, r=20, t=30, b=50),
        height=300,
    )

    return fig


def build_graph_with_title(df, x_axis, y_axis, tag):
    """
    Build a scatter plot with a title (used for PDF reports).

    Same as build_graph but adds a title and hides the legend to save space.
    """
    fig = build_graph(df, x_axis, y_axis, tag)
    title = f"{AXIS_SHORT_LABELS.get(y_axis, y_axis)} vs. {AXIS_SHORT_LABELS.get(x_axis, x_axis)}"
    fig.update_layout(
        title=dict(text=title, font=dict(size=12)),
        showlegend=False,
        height=250,
    )
    return fig
