"""
Player information card.

Layout   : pitcher photo + bio details (mirrors the PDF's top-left section).
Callback : updates when a new pitcher is selected from the dropdown.
"""

from __future__ import annotations

from dash import Input, Output, callback, html
import dash_bootstrap_components as dbc

from python_app.lib.cache import cache
from python_app.lib.styles import info_card


# ═══════════════════════════════════════════════════════════════════════════════
#  Layout
# ═══════════════════════════════════════════════════════════════════════════════

def layout():
    """Card with pitcher photo (left) and bio text (right)."""
    return info_card(
        "Pitcher Information",
        dbc.Row([
            dbc.Col(
                html.Div(id="player-photo", className="player-photo"),
                width=5,
            ),
            dbc.Col(
                html.Div(id="player-info", className="player-bio"),
                width=7,
            ),
        ], className="align-items-start"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Dash callback
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("player-photo", "children"),
    Output("player-info", "children"),
    Input("selected-player", "value"),
)
def update_player_info(selected_playerlinkid: str | None):
    """Refresh the player card when a new pitcher is chosen."""
    player = cache.get_player(selected_playerlinkid)
    if player is None:
        return "", ""

    # Photo
    img_url = player.get("photo", "")
    photo = (
        html.Img(
            src=img_url,
            style={
                "width": "100%",
                "borderRadius": "6px",
                "border": "2px solid #dcdde1",
            },
        )
        if img_url
        else html.P(
            "No photo available.",
            style={"color": "#999", "fontStyle": "italic"},
        )
    )

    # Bio fields — same fields as the PDF bio section
    bio_fields = [
        ("Name",     player["full_name"]),
        ("Team",     player.get("teamname", "")),
        ("Throws",   player.get("throws", "")),
        ("Bats",     player.get("bats", "")),
        ("Height",   player.get("height", "")),
        ("Weight",   player.get("weight", "")),
        ("Hometown", player.get("hometown", "")),
    ]

    info = html.Div(
        style={"marginTop": "4px"},
        children=[
            html.Div(
                [html.B(f"{label}: "), str(value)],
                style={
                    "padding": "3px 0",
                    "fontSize": "0.88rem",
                    "borderBottom": "1px solid #f5f6fa",
                },
            )
            for label, value in bio_fields
            if value
        ],
    )
    return photo, info
