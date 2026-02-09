"""
ALPB Pitching Widget — application entry point.

Assembles the page layout from feature modules and starts the Dash server.
Each feature module (features/) owns its own layout fragment and callbacks.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dash import Dash, html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd

from python_app.lib.cache import cache

# Import feature modules — this registers their callbacks with Dash
from python_app.features import (        # noqa: F401
    player_info,
    season_stats,
    scatter_plots,
    heatmaps,
    pitch_split,
    pdf_export,
)

# ── Bootstrap the data cache ────────────────────────────────────────────────
print("Loading pitcher roster...")
cache.load_roster()

# ── Dash app ────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "ALPB Pitchers"


# ── Page layout (assembled from features) ───────────────────────────────────
app.layout = dbc.Container(fluid=True, children=[
    # Loading overlay
    dcc.Loading(id="loading-overlay", type="default", fullscreen=True,
                children=html.Div(id="pdf-download-trigger")),

    html.H1("ALPB Pitchers", className="text-center my-3"),

    # Row 1 — pitcher selector + PDF button
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody(
            dcc.Dropdown(
                id="selected-player",
                options=[{"label": n, "value": n} for n in cache.pitcher_names],
                value=cache.pitcher_names[0] if cache.pitcher_names else None,
                placeholder="Choose a Pitcher...",
            ),
        )), width=4),
        dbc.Col(width=6),
        dbc.Col(
            dbc.Button("Download PDF", id="download-pdf-btn", color="primary"),
            width=2, className="d-flex align-items-center",
        ),
    ], className="mb-3"),
    dcc.Download(id="download-pdf"),

    # Row 2 — player info + season stats
    dbc.Row([
        dbc.Col(player_info.layout(), width=4),
        dbc.Col(season_stats.layout(), width=8),
    ], className="mb-3"),

    # Rows 3–6 — ALPB data (hidden when unavailable)
    html.Div(id="alpb-rows", children=[
        # Scatter plots
        dbc.Row([
            dbc.Col(scatter_plots.layout_vel(), width=6),
            dbc.Col(scatter_plots.layout_break(), width=6),
        ], className="mb-3"),

        # Controls
        dbc.Row([
            dbc.Col([
                html.Label("Break Type:", className="fw-bold"),
                dcc.RadioItems(
                    id="break-type",
                    options=[
                        {"label": "Vertical Break", "value": "induced_vert_break"},
                        {"label": "Horizontal Break", "value": "horz_break"},
                    ],
                    value="induced_vert_break",
                    labelStyle={"display": "block"},
                ),
            ], width=3),
            dbc.Col([
                html.Label("Pitch Tagging Method:", className="fw-bold"),
                dcc.RadioItems(
                    id="tag-choice",
                    options=[
                        {"label": "Machine Tagged", "value": "auto_pitch_type"},
                        {"label": "Human Tagged", "value": "tagged_pitch_type"},
                    ],
                    value="auto_pitch_type",
                    labelStyle={"display": "block"},
                ),
            ], width=3),
            dbc.Col([
                html.Label("Select Pitch Type:", className="fw-bold"),
                dcc.Dropdown(
                    id="selected-pitch-type",
                    options=[{"label": "All", "value": "All"}],
                    value="All",
                ),
            ], width=3),
        ], className="mb-3"),

        # Heatmaps
        dbc.Row([
            dbc.Col(heatmaps.layout_right(), width=6),
            dbc.Col(heatmaps.layout_left(), width=6),
        ], className="mb-3"),

        # Pitch split table
        dbc.Row(dbc.Col(pitch_split.layout(), width=12), className="mb-3"),
    ]),

    # Hidden stores
    dcc.Store(id="alpb-player-id-store"),
    dcc.Store(id="pitch-data-store"),
])


# ── Global callbacks (data plumbing between features) ───────────────────────

@callback(Output("alpb-player-id-store", "data"), Input("selected-player", "value"))
def lookup_alpb_id(name):
    return cache.get_alpb_id(name) if name else None


@callback(Output("pitch-data-store", "data"), Input("alpb-player-id-store", "data"))
def fetch_pitch_data(player_id):
    return cache.get_pitch_data(player_id) if player_id else None


@callback(Output("alpb-rows", "style"), Input("alpb-player-id-store", "data"))
def toggle_alpb_rows(player_id):
    return {"display": "block"} if player_id else {"display": "none"}


@callback(
    Output("selected-pitch-type", "options"),
    Output("selected-pitch-type", "value"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_pitch_type_options(records, tag):
    default = [{"label": "All", "value": "All"}]
    if not records:
        return default, "All"
    df = pd.DataFrame(records)
    if tag not in df.columns:
        return default, "All"
    types = sorted(t for t in df[tag].dropna().unique() if t != "Undefined")
    return default + [{"label": t, "value": t} for t in types], "All"


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
