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
import threading
import traceback

# Ensure the project root is on sys.path so ``python -m python_app.app``
# works regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dash import Dash, Input, Output, State, callback, dcc, html
import dash_bootstrap_components as dbc
import pandas as pd

from python_app.config import BATTER_SIDE_ALL, BATTER_SIDE_LABELS
from python_app.lib.cache import cache
from python_app.lib.filters import known_pitch_types
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

# Roster-refresh Interval cadence (ms): poll fast until the roster first loads,
# then slow to a periodic refresh so newly signed pitchers surface over time
# without a container restart.
ROSTER_REFRESH_FAST_MS = 2000
ROSTER_REFRESH_SLOW_MS = 300_000


# ── Bootstrap the data cache (non-blocking) ──────────────────────────────────
# Load the roster in a background thread so the web worker starts serving
# immediately. Loading synchronously here blocks gunicorn's worker from binding,
# so the host never becomes reachable. The team/pitcher dropdowns are filled in
# by `refresh_team_options` + `update_player_dropdown` once the load finishes
# (driven by the "roster-refresh" Interval in the layout). The same helper is
# re-spawned periodically to pick up newly signed pitchers.
def _load_roster_bg() -> None:
    print("Loading pitcher roster (background)...")
    try:
        refreshed = cache.refresh_roster_if_stale()
        if not refreshed:
            return  # another thread already handled it, or roster still fresh
        if not cache.pitchers_df.empty:
            print("Pitcher roster loaded.")
        else:
            print("Roster still empty; will retry on the next refresh tick.")
    except Exception:
        print("Failed to load roster; serving with empty data until it retries.")
        traceback.print_exc()


threading.Thread(target=_load_roster_bg, daemon=True).start()

# ── Dash app ─────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    url_base_pathname=os.getenv("DASH_URL_BASE_PATHNAME", "/"),
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "ALPB Pitchers — Scouting Report"
server = app.server


@server.route("/healthz")
def healthz():
    """Lightweight endpoint for uptime probes."""
    return {"status": "ok"}, 200


_ALL_TEAMS = "__ALL_TEAMS__"


def _build_player_options(team_name: str | None) -> list[dict[str, str]]:
    """Build dropdown options using unique ``iscore_guid`` values."""
    team_filter = None if team_name in (None, _ALL_TEAMS) else team_name
    df = cache.get_players(team_filter)
    if df.empty:
        return []

    display = df.sort_values(
        ["lname", "fname", "teamname", "iscore_guid"],
        na_position="last",
    )
    show_team = team_filter is None
    options: list[dict[str, str]] = []
    for _, row in display.iterrows():
        player_id = str(row.get("iscore_guid", "")).strip()
        if player_id.lower() in {"", "nan", "none", "null"}:
            continue
        label = str(row.get("full_name", "")).strip()
        team = str(row.get("teamname", "")).strip()
        if show_team and team:
            label = f"{label} ({team})"
        options.append({"label": label, "value": player_id})
    return options


# Built at import, before the background roster load finishes, so start with
# just "All Teams"; `refresh_team_options` adds the teams once data is ready.
_TEAM_OPTIONS = [{"label": "All Teams", "value": _ALL_TEAMS}]
_INITIAL_PLAYER_OPTIONS: list[dict[str, str]] = []
_INITIAL_PLAYER_VALUE = None


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
                    xs=12, md=3,
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
                    xs=12, md=4,
                ),
                dbc.Col(xs=12, md=1, className="d-none d-md-block"),
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
                    xs=12,
                    md=4,
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
            dbc.Col(player_info.layout(), xs=12, md=3),
            dbc.Col(season_stats.layout(), xs=12, md=9),
        ], className="gx-3 mb-3"),

        # ── ALPB Trackman sections (hidden when no ALPB data) ─────────
        html.Div(id="alpb-rows", children=[

            # Section 2: Pitch Movement (scatter plots)
            section_label("Pitch Movement"),
            dbc.Row([
                dbc.Col(scatter_plots.layout_vel(), xs=12, md=6),
                dbc.Col(scatter_plots.layout_break(), xs=12, md=6),
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
                        ], xs=12, md=3),
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
                        ], xs=12, md=3),
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
                        ], xs=12, md=3),
                        dbc.Col([
                            html.Label(
                                "Batter Side:",
                                className="fw-bold mb-1",
                            ),
                            dcc.RadioItems(
                                id="batter-side",
                                options=[
                                    {"label": " All", "value": BATTER_SIDE_ALL},
                                    {"label": f" {BATTER_SIDE_LABELS['Right']}",
                                     "value": "Right"},
                                    {"label": f" {BATTER_SIDE_LABELS['Left']}",
                                     "value": "Left"},
                                ],
                                value=BATTER_SIDE_ALL,
                                labelStyle={
                                    "display": "block",
                                    "marginBottom": "3px",
                                },
                            ),
                        ], xs=12, md=3),
                    ], className="align-items-start"),
                ]),
                xs=12,
            ), className="mb-3"),

            # Section 3: Pitch Heatmaps
            section_label("Pitch Heatmaps"),
            dbc.Row([
                dbc.Col(heatmaps.layout_right(), xs=12, md=6),
                dbc.Col(heatmaps.layout_left(), xs=12, md=6),
            ], className="gx-3 mb-3"),

            # Section 4: Pitch Usage by Count
            section_label("Pitch Usage by Count"),
            dbc.Row(
                dbc.Col(pitch_split.layout(), xs=12),
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

    # Polls the cache fast at startup until the roster first loads, then slows
    # to a periodic refresh (never disabled) so newly signed pitchers appear
    # without a container restart (see refresh_team_options / slow_roster_polling).
    dcc.Interval(
        id="roster-refresh",
        interval=ROSTER_REFRESH_FAST_MS,
        n_intervals=0,
        disabled=False,
    ),
])


# ═══════════════════════════════════════════════════════════════════════════════
#  Global callbacks — data plumbing between features
# ═══════════════════════════════════════════════════════════════════════════════

@callback(Output("alpb-player-id-store", "data"), Input("selected-player", "value"))
def lookup_alpb_id(iscore_guid: str | None):
    """Resolve the selected iScore GUID to an ALPB Trackman player ID."""
    return cache.get_alpb_id(iscore_guid) if iscore_guid else None


@callback(
    Output("selected-team", "options"),
    Input("roster-refresh", "n_intervals"),
)
def refresh_team_options(_n_intervals: int):
    """Fill the team dropdown, and kick off a non-blocking background roster
    refresh whenever the roster has gone stale so newly signed pitchers appear
    without a container restart."""
    if cache.roster_is_stale():
        threading.Thread(target=_load_roster_bg, daemon=True).start()
    return [{"label": "All Teams", "value": _ALL_TEAMS}] + [
        {"label": team, "value": team} for team in cache.team_names
    ]


@callback(
    Output("roster-refresh", "interval"),
    Input("selected-team", "options"),
)
def slow_roster_polling(team_options: list[dict[str, str]] | None):
    """Once real teams (beyond 'All Teams') have loaded, slow the roster-refresh
    Interval from the fast startup poll to a periodic cadence. The Interval is
    never disabled — it keeps refreshing the roster on a schedule."""
    loaded = bool(team_options) and len(team_options) > 1
    return ROSTER_REFRESH_SLOW_MS if loaded else ROSTER_REFRESH_FAST_MS


@callback(
    Output("selected-player", "options"),
    Output("selected-player", "value"),
    Input("selected-team", "value"),
    Input("roster-refresh", "n_intervals"),
    State("selected-player", "value"),
)
def update_player_dropdown(
    selected_team: str | None,
    _n_intervals: int,
    current_iscore_guid: str | None,
):
    """Filter player options by team; also refresh as the roster streams in."""
    options = _build_player_options(selected_team)
    valid_values = {opt["value"] for opt in options}
    if current_iscore_guid in valid_values:
        return options, current_iscore_guid
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
    types = known_pitch_types(df, tag)
    return default + [{"label": t, "value": t} for t in types], "All"


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8050"))
    debug = os.getenv("DASH_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
