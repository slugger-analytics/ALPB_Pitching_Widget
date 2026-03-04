"""
Season statistics table.

Layout   : single card showing ERA, WHIP, K, etc.
Callback : fetches stats via the data cache when a pitcher is selected.
"""

from __future__ import annotations

from dash import Input, Output, callback, html

from python_app.lib.cache import cache
from python_app.lib.styles import info_card, styled_table


# ═══════════════════════════════════════════════════════════════════════════════
#  Layout
# ═══════════════════════════════════════════════════════════════════════════════

def layout():
    """Card wrapping the season-stats table."""
    return info_card("Season Stats", html.Div(id="season-stats-output"))


# ═══════════════════════════════════════════════════════════════════════════════
#  Dash callback
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("season-stats-output", "children"),
    Input("selected-player", "value"),
)
def update_season_stats(selected_playerlinkid: str | None):
    """Refresh the stats table when a new pitcher is chosen."""
    player = cache.get_player(selected_playerlinkid)
    if player is None:
        return "Select a pitcher."

    stats = cache.get_season_stats(player["playerlinkid"])
    if stats is None or stats.empty:
        return html.P("No season stats found for this player.")

    return styled_table(stats, uppercase_columns=True)
