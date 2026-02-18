"""
Strike-zone heatmaps.

Layout   : two cards — pitch density vs RHB and vs LHB.
Callback : re-renders when pitch data, tag method, or pitch-type filter changes.
Builder  : ``build_heatmap`` is the single source of truth — also importable by
           other modules (e.g. future multi-page PDF heatmap sheets).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import gaussian_kde

from dash import Input, Output, callback, dcc

from python_app.lib.styles import info_card


# ═══════════════════════════════════════════════════════════════════════════════
#  Layout fragments
# ═══════════════════════════════════════════════════════════════════════════════

def layout_right():
    """Card for the RHB heatmap."""
    return info_card("Pitch map vs RH Batters", dcc.Graph(id="heatmap-right"))


def layout_left():
    """Card for the LHB heatmap."""
    return info_card("Pitch map vs LH Batters", dcc.Graph(id="heatmap-left"))


# ═══════════════════════════════════════════════════════════════════════════════
#  Public chart builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_heatmap(df: pd.DataFrame | None) -> go.Figure:
    """Build a Plotly heatmap of pitch locations over the strike zone.

    Uses 2-D Gaussian KDE (``scipy.stats.gaussian_kde``) to estimate
    density.  Returns a figure with just the strike-zone outline when
    there aren't enough data points.
    """
    fig = go.Figure()

    # Strike-zone rectangle
    sz_x = [-10 / 12, 10 / 12, 10 / 12, -10 / 12, -10 / 12]
    sz_y = [1.5, 1.5, 3.5, 3.5, 1.5]
    fig.add_trace(go.Scatter(
        x=sz_x, y=sz_y, mode="lines",
        line=dict(color="black", width=2),
        showlegend=False,
    ))

    # ── Prepare valid location data ───────────────────────────────────────
    if df is not None and not df.empty:
        loc = df[["plate_loc_side", "plate_loc_height"]].copy()
        loc["plate_loc_side"] = pd.to_numeric(loc["plate_loc_side"], errors="coerce")
        loc["plate_loc_height"] = pd.to_numeric(loc["plate_loc_height"], errors="coerce")
        loc = loc.dropna()
        loc = loc[
            np.isfinite(loc["plate_loc_side"])
            & np.isfinite(loc["plate_loc_height"])
        ]
    else:
        loc = pd.DataFrame()

    # ── KDE heatmap ───────────────────────────────────────────────────────
    if not loc.empty and len(loc) >= 2:
        x_vals = loc["plate_loc_side"].values
        y_vals = loc["plate_loc_height"].values
        xg = np.linspace(-1.5, 1.5, 300)
        yg = np.linspace(0, 4, 300)
        xx, yy = np.meshgrid(xg, yg)

        try:
            kernel = gaussian_kde(np.vstack([x_vals, y_vals]), bw_method=0.25)
            z = kernel(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
            z[z < 0.001] = np.nan

            fig.add_trace(go.Heatmap(
                x=xg, y=yg, z=z,
                colorscale=[
                    [0, "white"], [0.25, "blue"], [0.5, "green"],
                    [0.75, "yellow"], [1.0, "red"],
                ],
                showscale=False,
                zsmooth="best",
            ))
        except np.linalg.LinAlgError:
            pass  # degenerate data — skip the heatmap layer

    # ── Axis / layout ─────────────────────────────────────────────────────
    fig.update_layout(
        xaxis=dict(
            range=[-16 / 12, 16 / 12],
            showticklabels=False, showgrid=False, zeroline=False,
        ),
        yaxis=dict(
            range=[1, 4],
            showticklabels=False, showgrid=False, zeroline=False,
            scaleanchor="x", scaleratio=1,
        ),
        template="plotly_white",
        margin=dict(l=10, r=10, t=30, b=10),
        height=300,
        plot_bgcolor="white",
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _filter_by_side(
    pitch_records: list[dict] | None,
    tag: str,
    pitch_type: str | None,
    batter_side: str,
) -> pd.DataFrame:
    """Subset pitch records for one batter side and (optionally) pitch type."""
    if not pitch_records:
        return pd.DataFrame()
    df = pd.DataFrame(pitch_records)
    df = df[df["batter_side"] == batter_side]
    if pitch_type and pitch_type != "All" and tag in df.columns:
        df = df[df[tag] == pitch_type]
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  Dash callbacks
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("heatmap-right", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
    Input("selected-pitch-type", "value"),
)
def update_heatmap_right(
    pitch_records: list[dict] | None,
    tag: str,
    pitch_type: str | None,
) -> go.Figure:
    return build_heatmap(_filter_by_side(pitch_records, tag, pitch_type, "Right"))


@callback(
    Output("heatmap-left", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
    Input("selected-pitch-type", "value"),
)
def update_heatmap_left(
    pitch_records: list[dict] | None,
    tag: str,
    pitch_type: str | None,
) -> go.Figure:
    return build_heatmap(_filter_by_side(pitch_records, tag, pitch_type, "Left"))
