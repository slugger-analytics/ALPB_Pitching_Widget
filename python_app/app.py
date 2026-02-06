"""
ALPB Pitching Widget - Dash Application.

Interactive web dashboard for analyzing Atlantic League pitcher performance.
Equivalent to App.R (the R Shiny application).
"""

import base64
import os
import sys

# Allow imports from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dash import Dash, html, dcc, dash_table, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import pandas as pd

from python_app.api.pointstreak import get_all_pitchers, get_pitching_stats
from python_app.api.alpb import get_alpb_pitcher_info, get_alpb_pitches
from python_app.visualizations.graphs import build_graph
from python_app.visualizations.heatmap import build_heatmap
from python_app.analysis.pitch_split import get_pitch_type_percentages
from python_app.reports.pdf_report import generate_pdf

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
print("Loading pitcher roster...")
pitchers_df = get_all_pitchers()
pitcher_names = pitchers_df["full_name"].tolist() if not pitchers_df.empty else []

# ---------------------------------------------------------------------------
# Caches (equivalent to Shiny's bindCache)
# ---------------------------------------------------------------------------
_alpb_id_cache = {}
_pitch_data_cache = {}

# ---------------------------------------------------------------------------
# Helper: Bootstrap card with header
# ---------------------------------------------------------------------------

def card_with_header(title_id_or_str, body, card_id=None):
    """Create a Bootstrap card with an info-colored header."""
    if isinstance(title_id_or_str, str):
        header_content = title_id_or_str
    else:
        header_content = title_id_or_str

    props = {}
    if card_id:
        props["id"] = card_id

    return html.Div(
        className="card",
        children=[
            html.Div(
                header_content,
                className="card-header bg-info text-white text-center fw-bold",
                style={"paddingTop": "5px", "paddingBottom": "5px"},
            ),
            html.Div(
                html.Div(body, style={"textAlign": "center", "width": "100%"}),
                className="card-body d-flex justify-content-center align-items-center",
            ),
        ],
        **props,
    )


# ---------------------------------------------------------------------------
# App & layout
# ---------------------------------------------------------------------------
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "ALPB Pitchers"

app.layout = dbc.Container(
    fluid=True,
    children=[
        # Loading spinner overlay
        dcc.Loading(
            id="loading-overlay",
            type="default",
            fullscreen=True,
            children=html.Div(id="pdf-download-trigger"),
        ),

        # Title
        html.H1("ALPB Pitchers", className="text-center my-3"),

        # Row 1: Dropdown + PDF button
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            dcc.Dropdown(
                                id="selected-player",
                                options=[{"label": n, "value": n} for n in pitcher_names],
                                value=pitcher_names[0] if pitcher_names else None,
                                placeholder="Choose a Pitcher...",
                            )
                        )
                    ),
                    width=4,
                ),
                dbc.Col(width=6),
                dbc.Col(
                    html.A(
                        dbc.Button("Download PDF", id="download-pdf-btn", color="primary"),
                    ),
                    width=2,
                    className="d-flex align-items-center",
                ),
            ],
            className="mb-3",
        ),
        dcc.Download(id="download-pdf"),

        # Row 2: Pitcher info + Season stats
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        card_with_header(
                            "Pitcher Information",
                            dbc.Row(
                                [
                                    dbc.Col(html.Div(id="player-photo"), width=6),
                                    dbc.Col(html.Div(id="player-info"), width=6),
                                ]
                            ),
                        ),
                        style={"marginBottom": "20px"},
                    ),
                    width=4,
                ),
                dbc.Col(
                    card_with_header("Season Stats", html.Div(id="season-stats-output")),
                    width=8,
                ),
            ],
            className="mb-3",
        ),

        # Row 3: Scatter plots (hidden when no ALPB data)
        html.Div(
            id="alpb-rows",
            children=[
                dbc.Row(
                    [
                        dbc.Col(
                            card_with_header(
                                html.Span(id="scatter-header"),
                                dcc.Graph(id="vel-plot"),
                            ),
                            width=6,
                        ),
                        dbc.Col(
                            card_with_header(
                                "Induced Vertical Break vs Horizontal Break",
                                dcc.Graph(id="break-plot"),
                            ),
                            width=6,
                        ),
                    ],
                    className="mb-3",
                ),

                # Row 4: Controls
                dbc.Row(
                    [
                        dbc.Col(
                            [
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
                            ],
                            width=3,
                        ),
                        dbc.Col(
                            [
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
                            ],
                            width=3,
                        ),
                        dbc.Col(
                            html.Div([
                                html.Label("Select Pitch Type:", className="fw-bold"),
                                dcc.Dropdown(
                                    id="selected-pitch-type",
                                    options=[{"label": "All", "value": "All"}],
                                    value="All",
                                ),
                            ]),
                            width=3,
                        ),
                    ],
                    className="mb-3",
                ),

                # Row 5: Heatmaps
                dbc.Row(
                    [
                        dbc.Col(
                            card_with_header(
                                "Pitch map vs RH Batters",
                                dcc.Graph(id="heatmap-right"),
                            ),
                            width=6,
                        ),
                        dbc.Col(
                            card_with_header(
                                "Pitch map vs LH Batters",
                                dcc.Graph(id="heatmap-left"),
                            ),
                            width=6,
                        ),
                    ],
                    className="mb-3",
                ),

                # Row 6: Pitch split table
                dbc.Row(
                    dbc.Col(
                        card_with_header(
                            "Pitch Type Percentages for Each Count",
                            html.Div(id="pitch-table-container"),
                        ),
                        width=12,
                    ),
                    className="mb-3",
                ),
            ],
        ),

        # Hidden stores for cached data
        dcc.Store(id="alpb-player-id-store"),
        dcc.Store(id="pitch-data-store"),
    ],
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("player-photo", "children"),
    Output("player-info", "children"),
    Input("selected-player", "value"),
)
def update_player_info(selected_name):
    """Display pitcher profile card."""
    if not selected_name or pitchers_df.empty:
        return "", ""

    row = pitchers_df[pitchers_df["full_name"] == selected_name]
    if row.empty:
        return "", ""
    player = row.iloc[0]

    # Photo
    img_url = player.get("photo", "")
    if img_url:
        photo = html.Img(src=img_url, style={"width": "100%", "borderRadius": "8px"})
    else:
        photo = html.P("No photo available.")

    # Info
    info = html.Div(
        style={"textAlign": "left", "marginTop": "2vh"},
        children=[
            html.Div([html.B("Name: "), player["full_name"]]),
            html.Div([html.B("Team: "), player.get("teamname", "")]),
            html.Div([html.B("Player ID: "), player.get("playerid", "")]),
            html.Div([html.B("Hometown: "), player.get("hometown", "")]),
            html.Div([html.B("Throws: "), player.get("throws", "")]),
            html.Div([html.B("Weight: "), player.get("weight", "")]),
            html.Div([html.B("Height: "), player.get("height", "")]),
            html.Div([html.B("Bats: "), player.get("bats", "")]),
        ],
    )
    return photo, info


@callback(
    Output("season-stats-output", "children"),
    Input("selected-player", "value"),
)
def update_season_stats(selected_name):
    """Display season stats table."""
    if not selected_name or pitchers_df.empty:
        return "Select a pitcher."

    row = pitchers_df[pitchers_df["full_name"] == selected_name]
    if row.empty:
        return "Player not found."

    playerlinkid = row.iloc[0]["playerlinkid"]
    try:
        stats = get_pitching_stats(playerlinkid)
    except Exception:
        return html.P("Error loading season stats.")

    if stats is None or stats.empty:
        return html.P("No season stats found for this player.")

    return dash_table.DataTable(
        data=stats.to_dict("records"),
        columns=[{"name": c, "id": c} for c in stats.columns],
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#17a2b8", "color": "white", "fontWeight": "bold"},
        style_cell={"textAlign": "center", "padding": "5px", "fontSize": "12px"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f9f9f9"},
        ],
    )


@callback(
    Output("alpb-player-id-store", "data"),
    Input("selected-player", "value"),
)
def lookup_alpb_id(selected_name):
    """Look up ALPB player ID and cache it."""
    if not selected_name or pitchers_df.empty:
        return None

    if selected_name in _alpb_id_cache:
        return _alpb_id_cache[selected_name]

    row = pitchers_df[pitchers_df["full_name"] == selected_name]
    if row.empty:
        return None

    player = row.iloc[0]
    result = get_alpb_pitcher_info(player["fname"], player["lname"])

    if result is None:
        _alpb_id_cache[selected_name] = None
        return None

    _alpb_id_cache[selected_name] = result["player_id"]
    return result["player_id"]


@callback(
    Output("pitch-data-store", "data"),
    Input("alpb-player-id-store", "data"),
)
def fetch_pitch_data(player_id):
    """Fetch pitch-by-pitch data and cache it."""
    if not player_id:
        return None

    if player_id in _pitch_data_cache:
        return _pitch_data_cache[player_id]

    df = get_alpb_pitches(player_id)
    if df is None or df.empty:
        return None

    data = df.to_dict("records")
    _pitch_data_cache[player_id] = data
    return data


@callback(
    Output("alpb-rows", "style"),
    Input("alpb-player-id-store", "data"),
)
def toggle_alpb_visibility(player_id):
    """Show/hide ALPB rows based on data availability."""
    if player_id:
        return {"display": "block"}
    return {"display": "none"}


@callback(
    Output("scatter-header", "children"),
    Input("break-type", "value"),
)
def update_scatter_header(break_type):
    """Update the scatter plot header text."""
    if break_type == "induced_vert_break":
        return "Vertical Break vs Velocity"
    return "Horizontal Break vs Velocity"


@callback(
    Output("selected-pitch-type", "options"),
    Output("selected-pitch-type", "value"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_pitch_type_dropdown(pitch_records, tag):
    """Dynamically populate the pitch type filter dropdown options."""
    default_options = [{"label": "All", "value": "All"}]
    if not pitch_records:
        return default_options, "All"

    df = pd.DataFrame(pitch_records)
    if tag not in df.columns:
        return default_options, "All"

    types = df[tag].dropna().unique().tolist()
    types = [t for t in types if t != "Undefined"]
    options = default_options + [{"label": t, "value": t} for t in sorted(types)]

    return options, "All"


@callback(
    Output("vel-plot", "figure"),
    Input("pitch-data-store", "data"),
    Input("break-type", "value"),
    Input("tag-choice", "value"),
)
def update_vel_plot(pitch_records, break_type, tag):
    """Render the break-vs-velocity scatter plot."""
    if not pitch_records:
        return {}
    df = pd.DataFrame(pitch_records)
    return build_graph(df, "rel_speed", break_type, tag)


@callback(
    Output("break-plot", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_break_plot(pitch_records, tag):
    """Render the vertical-vs-horizontal break scatter plot."""
    if not pitch_records:
        return {}
    df = pd.DataFrame(pitch_records)
    return build_graph(df, "horz_break", "induced_vert_break", tag)


@callback(
    Output("heatmap-right", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
    Input("selected-pitch-type", "value"),
)
def update_heatmap_right(pitch_records, tag, pitch_type):
    """Render heatmap vs right-handed batters."""
    if not pitch_records:
        return {}
    df = pd.DataFrame(pitch_records)
    filtered = df[df["batter_side"] == "Right"]
    if pitch_type and pitch_type != "All" and tag in filtered.columns:
        filtered = filtered[filtered[tag] == pitch_type]
    return build_heatmap(filtered)


@callback(
    Output("heatmap-left", "figure"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
    Input("selected-pitch-type", "value"),
)
def update_heatmap_left(pitch_records, tag, pitch_type):
    """Render heatmap vs left-handed batters."""
    if not pitch_records:
        return {}
    df = pd.DataFrame(pitch_records)
    filtered = df[df["batter_side"] == "Left"]
    if pitch_type and pitch_type != "All" and tag in filtered.columns:
        filtered = filtered[filtered[tag] == pitch_type]
    return build_heatmap(filtered)


@callback(
    Output("pitch-table-container", "children"),
    Input("pitch-data-store", "data"),
    Input("tag-choice", "value"),
)
def update_pitch_table(pitch_records, tag):
    """Render pitch type percentages table."""
    if not pitch_records:
        return ""
    df = pd.DataFrame(pitch_records)
    split_df = get_pitch_type_percentages(df, tag)
    if split_df.empty:
        return html.P("No pitch split data available.")

    return dash_table.DataTable(
        data=split_df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in split_df.columns],
        page_size=12,
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#17a2b8", "color": "white", "fontWeight": "bold"},
        style_cell={"textAlign": "center", "padding": "5px", "fontSize": "12px"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f9f9f9"},
        ],
    )


@callback(
    Output("download-pdf", "data"),
    Input("download-pdf-btn", "n_clicks"),
    State("selected-player", "value"),
    State("alpb-player-id-store", "data"),
    State("pitch-data-store", "data"),
    State("tag-choice", "value"),
    prevent_initial_call=True,
)
def download_pdf(n_clicks, selected_name, alpb_id, pitch_records, tag):
    """Generate and download PDF report."""
    if not n_clicks or not selected_name:
        return no_update

    row = pitchers_df[pitchers_df["full_name"] == selected_name]
    if row.empty:
        return no_update

    playerlinkid = row.iloc[0]["playerlinkid"]
    stats = get_pitching_stats(playerlinkid)

    pitch_df = None
    if pitch_records:
        pitch_df = pd.DataFrame(pitch_records)

    pdf_path = generate_pdf(
        name=selected_name,
        season_stats=stats,
        pitch_data=pitch_df,
        pitch_tag=tag if tag else "auto_pitch_type",
    )

    return dcc.send_file(pdf_path, filename=f"{selected_name} Pitcher Report.pdf")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
