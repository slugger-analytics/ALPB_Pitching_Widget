"""
ALPB Pitching Widget — application entry point.

Assembles the page layout from feature modules and starts the Dash server.
Each feature module under ``features/`` owns its own layout fragment and
Dash callbacks; importing them is enough to register everything.

The visual style (navy banner, section labels, card colours) mirrors the
PDF export so the user sees the same brand identity everywhere.
"""

from __future__ import annotations

import os
import sys

# Ensure the project root is on sys.path so ``python -m python_app.app``
# works regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dash import Dash, Input, Output, callback, dcc, html
import dash_bootstrap_components as dbc
import pandas as pd

from python_app.lib.cache import cache
from python_app.lib.styles import section_label

# Importing feature modules registers their Dash callbacks.
from python_app.features import (  # noqa: F401
    heatmaps,
    pdf_export,
    pitch_split,
    player_info,
    scatter_plots,
    season_stats,
)

# ── Bootstrap the data cache ─────────────────────────────────────────────────
print("Loading pitcher roster...")
cache.load_roster()

# ── Dash app ─────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "ALPB Pitchers — Scouting Report"


# ═══════════════════════════════════════════════════════════════════════════════
#  Page layout — mirrors the PDF report flow:
#
#   ┌──────────────────────────────────────┐
#   │  Banner                              │
#   ├──────────────────────────────────────┤
#   │  [Selector ▾]           [📄 PDF]     │  toolbar
#   ├──────────────────────────────────────┤
#   │  PITCHER INFORMATION & SEASON STATS  │  section
#   │  [Photo + Bio]  │  [Stats table]     │
#   ├──────────────────────────────────────┤
#   │  PITCH MOVEMENT                      │  section
#   │  [Scatter 1]  [Scatter 2]            │
#   ├──────────────────────────────────────┤
#   │  ⚙ Controls                          │
#   ├──────────────────────────────────────┤
#   │  PITCH HEATMAPS                      │  section
#   │  [vs RHB]  [vs LHB]                  │
#   ├──────────────────────────────────────┤
#   │  PITCH USAGE BY COUNT                │  section
#   │  [split table]                       │
#   ├──────────────────────────────────────┤
#   │  Footer                              │
#   └──────────────────────────────────────┘
# ═══════════════════════════════════════════════════════════════════════════════

app.layout = dbc.Container(fluid=True, style={"padding": 0}, children=[

    # Loading overlay
    dcc.Loading(
        id="loading-overlay", type="default", fullscreen=True,
        children=html.Div(id="pdf-download-trigger"),
    ),

    # ── Banner ────────────────────────────────────────────────────────────
    html.Div(className="brand-banner text-center", children=[
        html.H1("ALPB Pitchers"),
        html.Div("Pitching Scouting Report Dashboard", className="subtitle"),
    ]),

    # ── Toolbar row (selector + PDF button) ──────────────────────────────
    html.Div(className="toolbar-row", children=[
        dbc.Container(fluid=True, style={"maxWidth": "1320px"}, children=[
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id="selected-player",
                        options=[
                            {"label": n, "value": n}
                            for n in cache.pitcher_names
                        ],
                        value=(
                            cache.pitcher_names[0]
                            if cache.pitcher_names else None
                        ),
                        placeholder="Choose a Pitcher...",
                        style={"fontSize": "0.92rem"},
                    ),
                    width=5,
                ),
                dbc.Col(width=5),
                dbc.Col(
                    html.Button(
                        "📄 Download PDF",
                        id="download-pdf-btn",
                        className="btn btn-brand w-100",
                    ),
                    width=2,
                    className="d-flex align-items-center",
                ),
            ], className="align-items-center"),
        ]),
    ]),
    dcc.Download(id="download-pdf"),

    # ── Main content ─────────────────────────────────────────────────────
    html.Div(className="content-wrapper", children=[

        # ── Section 1: Pitcher Info + Season Stats ────────────────────
        section_label("Pitcher Information & Season Stats"),
        dbc.Row([
            dbc.Col(player_info.layout(), width=4),
            dbc.Col(season_stats.layout(), width=8),
        ], className="gx-3 mb-3"),

        # ── ALPB Trackman sections (hidden when no ALPB data) ─────────
        html.Div(id="alpb-rows", children=[

            # Section 2: Pitch Movement (scatter plots)
            section_label("Pitch Movement"),
            dbc.Row([
                dbc.Col(scatter_plots.layout_vel(), width=6),
                dbc.Col(scatter_plots.layout_break(), width=6),
            ], className="gx-3 mb-3"),

            # Controls strip
            dbc.Row(dbc.Col(
                html.Div(className="controls-panel", children=[
                    dbc.Row([
                        dbc.Col([
                            html.Label("Break Type:", className="fw-bold mb-1"),
                            dcc.RadioItems(
                                id="break-type",
                                options=[
                                    {"label": " Vertical Break",
                                     "value": "induced_vert_break"},
                                    {"label": " Horizontal Break",
                                     "value": "horz_break"},
                                ],
                                value="induced_vert_break",
                                labelStyle={
                                    "display": "block",
                                    "marginBottom": "3px",
                                },
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label(
                                "Pitch Tagging Method:",
                                className="fw-bold mb-1",
                            ),
                            dcc.RadioItems(
                                id="tag-choice",
                                options=[
                                    {"label": " Machine Tagged",
                                     "value": "auto_pitch_type"},
                                    {"label": " Human Tagged",
                                     "value": "tagged_pitch_type"},
                                ],
                                value="auto_pitch_type",
                                labelStyle={
                                    "display": "block",
                                    "marginBottom": "3px",
                                },
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label(
                                "Select Pitch Type:",
                                className="fw-bold mb-1",
                            ),
                            dcc.Dropdown(
                                id="selected-pitch-type",
                                options=[{"label": "All", "value": "All"}],
                                value="All",
                                style={"fontSize": "0.88rem"},
                            ),
                        ], width=4),
                    ], className="align-items-start"),
                ]),
            ), className="mb-3"),

            # Section 3: Pitch Heatmaps
            section_label("Pitch Heatmaps"),
            dbc.Row([
                dbc.Col(heatmaps.layout_right(), width=6),
                dbc.Col(heatmaps.layout_left(), width=6),
            ], className="gx-3 mb-3"),

            # Section 4: Pitch Usage by Count
            section_label("Pitch Usage by Count"),
            dbc.Row(
                dbc.Col(pitch_split.layout(), width=12),
                className="mb-3",
            ),
        ]),

        # ── Footer ────────────────────────────────────────────────────
        html.Div(
            "Generated by SLUGGER Pitching Widget",
            className="app-footer",
        ),
    ]),

    # Hidden stores (data plumbing between features)
    dcc.Store(id="alpb-player-id-store"),
    dcc.Store(id="pitch-data-store"),
])


# ═══════════════════════════════════════════════════════════════════════════════
#  Global callbacks — data plumbing between features
# ═══════════════════════════════════════════════════════════════════════════════

@callback(Output("alpb-player-id-store", "data"), Input("selected-player", "value"))
def lookup_alpb_id(name: str | None):
    """Resolve the selected player name to an ALPB Trackman player ID."""
    return cache.get_alpb_id(name) if name else None


@callback(Output("pitch-data-store", "data"), Input("alpb-player-id-store", "data"))
def fetch_pitch_data(player_id: str | None):
    """Fetch raw pitch records for the selected ALPB player."""
    return cache.get_pitch_data(player_id) if player_id else None


@callback(Output("alpb-rows", "style"), Input("alpb-player-id-store", "data"))
def toggle_alpb_rows(player_id: str | None):
    """Show / hide the Trackman data sections depending on ALPB availability."""
    return {"display": "block"} if player_id else {"display": "none"}


@callback(
    Output("selected-pitch-type", "options"),
    Output("selected-pitch-type", "value"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_pitch_type_options(
    records: list[dict] | None,
    tag: str,
):
    """Populate the pitch-type filter dropdown from the loaded data."""
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
