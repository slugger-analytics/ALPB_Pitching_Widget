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

from dash import Dash, Input, Output, State, callback, dcc, html
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
server = app.server

_ALL_TEAMS = "__ALL_TEAMS__"


def _build_player_options(team_name: str | None) -> list[dict[str, str]]:
    """Build dropdown options using unique ``playerlinkid`` values."""
    team_filter = None if team_name in (None, _ALL_TEAMS) else team_name
    df = cache.get_players(team_filter)
    if df.empty:
        return []

    display = df.sort_values(
        ["lname", "fname", "teamname", "playerlinkid"],
        na_position="last",
    )
    show_team = team_filter is None
    options: list[dict[str, str]] = []
    for _, row in display.iterrows():
        player_id = str(row.get("playerlinkid", "")).strip()
        if player_id.lower() in {"", "nan", "none", "null"}:
            continue
        label = str(row.get("full_name", "")).strip()
        team = str(row.get("teamname", "")).strip()
        if show_team and team:
            label = f"{label} ({team})"
        options.append({"label": label, "value": player_id})
    return options


_TEAM_OPTIONS = [{"label": "All Teams", "value": _ALL_TEAMS}] + [
    {"label": team, "value": team} for team in cache.team_names
]
_INITIAL_PLAYER_OPTIONS = _build_player_options(_ALL_TEAMS)
_INITIAL_PLAYER_VALUE = (
    _INITIAL_PLAYER_OPTIONS[0]["value"] if _INITIAL_PLAYER_OPTIONS else None
)


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

    # ── Toolbar row (team/player selectors + PDF buttons) ────────────────
    html.Div(className="toolbar-row", children=[
        dbc.Container(fluid=True, style={"maxWidth": "1320px"}, children=[
            dbc.Row([
                dbc.Col(
                    html.Div([
                        html.Label("Team", className="toolbar-label"),
                        dcc.Dropdown(
                            id="selected-team",
                            options=_TEAM_OPTIONS,
                            value=_ALL_TEAMS,
                            clearable=False,
                            placeholder="Choose a Team...",
                            style={"fontSize": "0.92rem"},
                        ),
                    ]),
                    width=3,
                ),
                dbc.Col(
                    html.Div([
                        html.Label("Pitcher", className="toolbar-label"),
                        dcc.Dropdown(
                            id="selected-player",
                            options=_INITIAL_PLAYER_OPTIONS,
                            value=_INITIAL_PLAYER_VALUE,
                            clearable=False,
                            placeholder="Choose a Pitcher...",
                            style={"fontSize": "0.92rem"},
                        ),
                    ]),
                    width=4,
                ),
                dbc.Col(width=1),
                dbc.Col(
                    html.Div(className="d-grid gap-2", children=[
                        html.Button(
                            "📄 Download One-Page PDF",
                            id="download-pdf-btn",
                            className="btn btn-brand w-100",
                        ),
                        html.Button(
                            "📚 Download Team PDF",
                            id="download-team-pdf-btn",
                            className="btn btn-brand-outline w-100",
                        ),
                    ]),
                    width=4,
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
def lookup_alpb_id(playerlinkid: str | None):
    """Resolve the selected Pointstreak playerlinkid to an ALPB player ID."""
    return cache.get_alpb_id(playerlinkid) if playerlinkid else None


@callback(
    Output("selected-player", "options"),
    Output("selected-player", "value"),
    Input("selected-team", "value"),
    State("selected-player", "value"),
)
def update_player_dropdown(
    selected_team: str | None,
    current_playerlinkid: str | None,
):
    """Filter player options by team and keep current selection when valid."""
    options = _build_player_options(selected_team)
    valid_values = {opt["value"] for opt in options}
    if current_playerlinkid in valid_values:
        return options, current_playerlinkid
    next_value = options[0]["value"] if options else None
    return options, next_value


@callback(Output("download-team-pdf-btn", "style"), Input("selected-team", "value"))
def toggle_team_pdf_button(selected_team: str | None):
    """Show team-PDF button only when one specific team is selected."""
    if not selected_team or selected_team == _ALL_TEAMS:
        return {"display": "none"}
    return {"display": "block"}


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
    port = int(os.getenv("PORT", "8050"))
    debug = os.getenv("DASH_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
