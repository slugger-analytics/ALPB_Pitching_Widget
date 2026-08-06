"""HTTP routes behind the one-click team report.

The team report used to be built inside a Dash callback: one request that
rendered every pitcher on the roster. That request is minutes long — High Point
(34 pitchers) returned **504 after the ALB's 300s idle timeout**, and Charleston
(16 pitchers, warm cache) took 173.5s against gunicorn's 180s worker timeout, so
it was failing even when it appeared to work. No timeout value fixes that; the
request itself has to get shorter.

So the report is assembled in the browser. These routes hand out the roster and
then one single-page PDF at a time, and ``assets/team_pdf.js`` merges the pages
with pdf-lib. No single request is long, a failed pitcher costs one page instead
of the whole report, and the user watches it progress. This is the pattern
``slugger-outfielder`` already uses (commit ``aaf3330``).

Both routes mount under the Dash base path. Production runs
``DASH_URL_BASE_PATHNAME=/widgets/pitching/`` and the ALB forwards the full path,
so anything registered at the root is unreachable — ``/healthz`` already is.
"""

from __future__ import annotations

from flask import Flask, Response, jsonify, request

from python_app.config import BATTER_SIDE_ALL
from python_app.features.pdf_export import (
    _filename_side_suffix,
    _pitch_df_for_player,
    _safe_filename,
    _team_sorted,
    render_player_pdf_bytes,
)
from python_app.lib.cache import cache

_ALL_TEAMS = "__ALL_TEAMS__"

# Mirrors the "Pitch Tagging Method" radio. Anything else is a stale bookmark or
# a hand-edited URL, and silently falling back beats rendering a blank report.
_VALID_TAGS = frozenset({"auto_pitch_type", "tagged_pitch_type"})

# Mirrors the "Batter Side" radio; `filter_batter_side` treats "All" as no filter.
_VALID_SIDES = frozenset({"Right", "Left", BATTER_SIDE_ALL})

_MISSING_ID_PLACEHOLDERS = frozenset({"", "nan", "none", "null"})


def _roster_entries(team_name: str) -> tuple[list[dict[str, str]], int]:
    """Return ``(players, excluded)`` for *team_name*.

    Ordering and de-duplication come from ``_team_sorted`` — the same helper the
    old server-side loop used — so the merged report keeps the page order coaches
    already know.

    Records carrying no ``iscore_guid`` cannot be fetched individually, so they
    are excluded and counted rather than dropped in silence. They were already
    invisible in the pitcher dropdown, and their pages held no pitch data.
    """
    players = cache.get_players(team_name)
    if players is None or players.empty:
        return [], 0

    entries: list[dict[str, str]] = []
    excluded = 0
    for _, player in _team_sorted(players).iterrows():
        guid = str(player.get("iscore_guid", "")).strip()
        if guid.lower() in _MISSING_ID_PLACEHOLDERS:
            excluded += 1
            continue
        entries.append({
            "id": guid,
            "name": str(player.get("full_name", "")).strip() or "Pitcher",
        })
    return entries, excluded


def register_routes(server: Flask, base_path: str = "/") -> None:
    """Mount the team-report routes on *server* under *base_path*."""
    base = base_path if base_path.endswith("/") else f"{base_path}/"

    @server.route(f"{base}api/team-roster")
    def team_roster() -> Response:
        """The pitchers a team report covers, in page order."""
        team = (request.args.get("team") or "").strip()
        if not team or team == _ALL_TEAMS:
            return jsonify({"error": "a specific team is required"}), 400

        players, excluded = _roster_entries(team)
        return jsonify({"team": team, "players": players, "excluded": excluded})

    @server.route(f"{base}api/player-pdf")
    def player_pdf() -> Response:
        """One pitcher's report page, as a standalone PDF."""
        guid = (request.args.get("guid") or "").strip()
        player = cache.get_player_by_guid(guid) if guid else None
        if player is None:
            return jsonify({"error": "unknown pitcher"}), 404

        tag = request.args.get("tag") or "auto_pitch_type"
        if tag not in _VALID_TAGS:
            tag = "auto_pitch_type"
        side = request.args.get("side") or BATTER_SIDE_ALL
        if side not in _VALID_SIDES:
            side = BATTER_SIDE_ALL

        name = str(player.get("full_name", "")).strip() or "Pitcher"
        pdf_bytes = render_player_pdf_bytes(
            name=name,
            player=player,
            season_stats=cache.get_season_stats(guid),
            pitch_data=_pitch_df_for_player(player),
            pitch_tag=tag,
            batter_side=side,
        )

        filename = (
            f"{_safe_filename(name)} Pitcher Report"
            f"{_filename_side_suffix(side)}.pdf"
        )
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
