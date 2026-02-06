"""
Strike zone heatmap visualizations.

Generates 2D kernel density estimate heatmaps of pitch locations.
Equivalent to getHeatMap.R.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde


def build_heatmap(df):
    """
    Build a heatmap of pitch locations over the strike zone.

    Uses 2D kernel density estimation (KDE) to compute pitch density,
    then renders a colored heatmap with the strike zone boundary overlaid.

    Args:
        df: DataFrame with 'plate_loc_side' and 'plate_loc_height' columns.

    Returns:
        A Plotly Figure object.
    """
    fig = go.Figure()

    # Always draw the strike zone rectangle
    # Strike zone: x from -10/12 to 10/12 feet, y from 1.5 to 3.5 feet
    sz_x = [-10 / 12, 10 / 12, 10 / 12, -10 / 12, -10 / 12]
    sz_y = [1.5, 1.5, 3.5, 3.5, 1.5]
    fig.add_trace(
        go.Scatter(
            x=sz_x,
            y=sz_y,
            mode="lines",
            line=dict(color="black", width=2),
            showlegend=False,
        )
    )

    # Filter valid data
    if df is not None and not df.empty:
        plot_df = df[["plate_loc_side", "plate_loc_height"]].copy()
        plot_df["plate_loc_side"] = pd.to_numeric(plot_df["plate_loc_side"], errors="coerce")
        plot_df["plate_loc_height"] = pd.to_numeric(plot_df["plate_loc_height"], errors="coerce")
        plot_df = plot_df.dropna()
        plot_df = plot_df[np.isfinite(plot_df["plate_loc_side"]) & np.isfinite(plot_df["plate_loc_height"])]
    else:
        plot_df = pd.DataFrame()

    if not plot_df.empty and len(plot_df) >= 2:
        x = plot_df["plate_loc_side"].values
        y = plot_df["plate_loc_height"].values

        # KDE grid matching the R version
        x_grid = np.linspace(-1.5, 1.5, 100)
        y_grid = np.linspace(0, 4, 100)
        xx, yy = np.meshgrid(x_grid, y_grid)
        positions = np.vstack([xx.ravel(), yy.ravel()])

        try:
            kernel = gaussian_kde(np.vstack([x, y]), bw_method=1.0)
            z = kernel(positions).reshape(xx.shape)
        except np.linalg.LinAlgError:
            z = np.zeros(xx.shape)

        # Filter sparse densities (matching R: z > 0.001)
        z[z < 0.001] = np.nan

        fig.add_trace(
            go.Heatmap(
                x=x_grid,
                y=y_grid,
                z=z,
                colorscale=[
                    [0, "white"],
                    [0.25, "blue"],
                    [0.5, "green"],
                    [0.75, "yellow"],
                    [1.0, "red"],
                ],
                showscale=False,
                zsmooth="best",
            )
        )

    fig.update_layout(
        xaxis=dict(
            range=[-16 / 12, 16 / 12],
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            title="",
        ),
        yaxis=dict(
            range=[1, 4],
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            title="",
            scaleanchor="x",
            scaleratio=1,
        ),
        template="plotly_white",
        margin=dict(l=10, r=10, t=30, b=10),
        height=300,
        plot_bgcolor="white",
    )

    return fig


def build_heatmap_right(df):
    """Build heatmap filtered to right-handed batters."""
    if df is None or df.empty:
        return build_heatmap(pd.DataFrame())
    filtered = df[df["batter_side"] == "Right"]
    return build_heatmap(filtered)


def build_heatmap_left(df):
    """Build heatmap filtered to left-handed batters."""
    if df is None or df.empty:
        return build_heatmap(pd.DataFrame())
    filtered = df[df["batter_side"] == "Left"]
    return build_heatmap(filtered)


def build_all_three(df, pitch_name):
    """
    Build a 3-panel heatmap: vs All Batters, vs RHB, vs LHB.
    Used for PDF reports.

    Returns a Plotly Figure with 3 subplots.
    """
    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=[
            f"{pitch_name} vs All Batters",
            f"{pitch_name} vs RHB",
            f"{pitch_name} vs LHB",
        ],
        horizontal_spacing=0.05,
    )

    for col, sub_fig in enumerate(
        [build_heatmap(df), build_heatmap_right(df), build_heatmap_left(df)], start=1
    ):
        for trace in sub_fig.data:
            fig.add_trace(trace, row=1, col=col)

    # Apply strike zone axis settings to all subplots
    for i in range(1, 4):
        suffix = "" if i == 1 else str(i)
        fig.update_layout(
            **{
                f"xaxis{suffix}": dict(
                    range=[-16 / 12, 16 / 12],
                    showticklabels=False,
                    showgrid=False,
                ),
                f"yaxis{suffix}": dict(
                    range=[1, 4],
                    showticklabels=False,
                    showgrid=False,
                    scaleanchor=f"x{suffix}",
                    scaleratio=1,
                ),
            }
        )

    fig.update_layout(
        height=350,
        showlegend=False,
        template="plotly_white",
        margin=dict(l=10, r=10, t=50, b=10),
    )

    return fig
