"""
Player information card.

Layout: pitcher photo + bio details.
Callback: updates when a new pitcher is selected.
"""

from dash import html, callback, Input, Output
import dash_bootstrap_components as dbc

from python_app.lib.cache import cache
from python_app.lib.styles import info_card


# ── Layout ───────────────────────────────────────────────────────────────────

def layout():
    return info_card(
        "Pitcher Information",
        dbc.Row([
            dbc.Col(html.Div(id="player-photo"), width=6),
            dbc.Col(html.Div(id="player-info"), width=6),
        ]),
    )


# ── Callback ─────────────────────────────────────────────────────────────────

@callback(
    Output("player-photo", "children"),
    Output("player-info", "children"),
    Input("selected-player", "value"),
)
def update_player_info(selected_name):
    player = cache.get_player(selected_name)
    if player is None:
        return "", ""

    # Photo
    img_url = player.get("photo", "")
    if img_url:
        photo = html.Img(src=img_url, style={"width": "100%", "borderRadius": "8px"})
    else:
        photo = html.P("No photo available.")

    # Bio fields
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
