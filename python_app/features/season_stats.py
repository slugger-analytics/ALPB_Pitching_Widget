"""
Season statistics table.

Layout: single card showing ERA, WHIP, K, etc.
Callback: fetches stats via the data cache when a pitcher is selected.
"""

from dash import html, callback, Input, Output

from python_app.lib.cache import cache
from python_app.lib.styles import info_card, styled_table


# ── Layout ───────────────────────────────────────────────────────────────────

def layout():
    return info_card("Season Stats", html.Div(id="season-stats-output"))


# ── Callback ─────────────────────────────────────────────────────────────────

@callback(
    Output("season-stats-output", "children"),
    Input("selected-player", "value"),
)
def update_season_stats(selected_name):
    player = cache.get_player(selected_name)
    if player is None:
        return "Select a pitcher."

    stats = cache.get_season_stats(player["playerlinkid"])

    if stats is None or stats.empty:
        return html.P("No season stats found for this player.")

    return styled_table(stats)
