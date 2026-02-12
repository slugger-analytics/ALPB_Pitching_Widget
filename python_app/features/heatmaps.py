"""
Strike zone heatmaps.

Layout: two heatmap cards (vs RHB, vs LHB).
Callback: re-renders when pitch data, tag method, or pitch type filter changes.
Chart: 2D Gaussian KDE over the strike zone using scipy + Plotly.
"""

import plotly.graph_objects as go
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from dash import dcc, callback, Input, Output

from python_app.lib.styles import info_card


# ── Layout ───────────────────────────────────────────────────────────────────

def layout_right():
    return info_card("Pitch map vs RH Batters", dcc.Graph(id="heatmap-right"))


def layout_left():
    return info_card("Pitch map vs LH Batters", dcc.Graph(id="heatmap-left"))


# ── Chart builder ────────────────────────────────────────────────────────────

def build_heatmap(df):
    """Build a Plotly heatmap of pitch locations over the strike zone."""
    fig = go.Figure()

    # Strike zone rectangle
    sz_x = [-10 / 12, 10 / 12, 10 / 12, -10 / 12, -10 / 12]
    sz_y = [1.5, 1.5, 3.5, 3.5, 1.5]
    fig.add_trace(go.Scatter(
        x=sz_x, y=sz_y, mode="lines",
        line=dict(color="black", width=2), showlegend=False,
    ))

    # Prepare valid location data
    if df is not None and not df.empty:
        loc = df[["plate_loc_side", "plate_loc_height"]].copy()
        loc["plate_loc_side"] = pd.to_numeric(loc["plate_loc_side"], errors="coerce")
        loc["plate_loc_height"] = pd.to_numeric(loc["plate_loc_height"], errors="coerce")
        loc = loc.dropna()
        loc = loc[np.isfinite(loc["plate_loc_side"]) & np.isfinite(loc["plate_loc_height"])]
    else:
        loc = pd.DataFrame()

    if not loc.empty and len(loc) >= 2:
        x, y = loc["plate_loc_side"].values, loc["plate_loc_height"].values
        xg = np.linspace(-1.5, 1.5, 300)
        yg = np.linspace(0, 4, 300)
        xx, yy = np.meshgrid(xg, yg)

        try:
            kernel = gaussian_kde(np.vstack([x, y]), bw_method=.25)
            z = kernel(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
            z[z < 0.001] = np.nan
            fig.add_trace(go.Heatmap(
                x=xg, y=yg, z=z,
                colorscale=[
                    [0, "white"], [0.25, "blue"], [0.5, "green"],
                    [0.75, "yellow"], [1.0, "red"],
                ],
                showscale=False, zsmooth="best",
            ))
        except np.linalg.LinAlgError:
            pass

    fig.update_layout(
        xaxis=dict(range=[-16 / 12, 16 / 12], showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(range=[1, 4], showticklabels=False, showgrid=False, zeroline=False,
                   scaleanchor="x", scaleratio=1),
        template="plotly_white",
        margin=dict(l=10, r=10, t=30, b=10),
        height=300, plot_bgcolor="white",
    )
    return fig


# ── Callbacks ────────────────────────────────────────────────────────────────

def _filter(pitch_records, tag, pitch_type, batter_side):
    """Shared filtering logic for both heatmap callbacks."""
    if not pitch_records:
        return pd.DataFrame()
    df = pd.DataFrame(pitch_records)
    df = df[df["batter_side"] == batter_side]
    if pitch_type and pitch_type != "All" and tag in df.columns:
        df = df[df[tag] == pitch_type]
    return df


@callback(
    Output("heatmap-right", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
    Input("selected-pitch-type", "value"),
)
def update_heatmap_right(pitch_records, tag, pitch_type):
    return build_heatmap(_filter(pitch_records, tag, pitch_type, "Right"))


@callback(
    Output("heatmap-left", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
    Input("selected-pitch-type", "value"),
)
def update_heatmap_left(pitch_records, tag, pitch_type):
    return build_heatmap(_filter(pitch_records, tag, pitch_type, "Left"))
