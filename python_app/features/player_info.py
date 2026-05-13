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
    """Card with pitcher bio details."""
    return info_card(
        "Pitcher Information",
        html.Div(id="player-info", className="player-bio"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Dash callback
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("player-info", "children"),
    Input("selected-player", "value"),
)
def update_player_info(iscore_guid: str | None):
    """Refresh the player card when a new pitcher is chosen."""
    player = cache.get_player(iscore_guid)
    if player is None:
        return ""

    bio_fields = [
        ("Name",     player["full_name"]),
        ("Team",     player.get("teamname", "")),
        ("Throws",   player.get("throws", "")),
        ("Bats",     player.get("bats", "")),
        ("Height",   player.get("height", "")),
        ("Weight",   player.get("weight", "")),
        ("Hometown", player.get("hometown", "")),
    ]

    visible = [(label, str(value)) for label, value in bio_fields if value]

    return html.Div(
        className="player-bio",
        style={"marginTop": "4px"},
        children=[
            html.Div(
                [
                    html.Div(
                        [html.Span(f"{lbl}:", className="bio-label") for lbl, _ in visible],
                        className="bio-col-labels",
                    ),
                    html.Div(
                        [html.Span(val, className="bio-value") for _, val in visible],
                        className="bio-col-values",
                    ),
                ],
                className="bio-grid",
            )
        ],
    )
