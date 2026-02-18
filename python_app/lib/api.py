"""
API clients for Pointstreak and ALPB Trackman.

All external HTTP calls live here.  No caching — that responsibility
belongs to :mod:`python_app.lib.cache`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

from python_app.config import (
    ALPB_API_KEY,
    ALPB_BASE_URL,
    DEFAULT_SEASON_ID,
    EXCLUDED_TEAMS,
    LEAGUE_ID,
    MAX_WORKERS,
    POINTSTREAK_API_KEY,
    POINTSTREAK_BASE_URL,
)

# Persistent HTTP sessions for connection reuse
_ps_session = requests.Session()
_ps_session.headers.update({"apikey": POINTSTREAK_API_KEY})

_alpb_session = requests.Session()
_alpb_session.headers.update({"x-api-key": ALPB_API_KEY})


# ═══════════════════════════════════════════════════════════════════════════════
#  Pointstreak
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_all_pitchers(season_id: str = DEFAULT_SEASON_ID) -> pd.DataFrame:
    """Fetch every pitcher across all ALPB teams for *season_id*."""
    url = f"{POINTSTREAK_BASE_URL}/league/structure/{LEAGUE_ID}/json"

    res = _ps_session.get(url, params={"seasonid": season_id})
    res.raise_for_status()
    parsed = res.json()

    season = _find_season(parsed, season_id)
    if season is None:
        return pd.DataFrame()

    teams: list[dict] = []
    for div in season["division"]:
        teams.extend(div["team"])

    # Parallel roster fetching
    all_pitchers: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_team_pitchers, t, season_id): t for t in teams}
        for fut in as_completed(futures):
            try:
                all_pitchers.extend(fut.result())
            except Exception:
                continue

    if not all_pitchers:
        return pd.DataFrame()

    df = pd.DataFrame(all_pitchers)
    df = df[~df["teamname"].isin(EXCLUDED_TEAMS)]
    df = df.sort_values("lname").reset_index(drop=True)
    df["full_name"] = df["fname"] + " " + df["lname"]
    return df


def fetch_pitching_stats(
    playerlinkid: str,
    season_id: str = DEFAULT_SEASON_ID,
) -> pd.DataFrame | None:
    """Fetch aggregated season pitching stats for one player."""
    url = f"{POINTSTREAK_BASE_URL}/player/stats/{playerlinkid}/{season_id}/json"
    try:
        res = _ps_session.get(url)
        if res.status_code != 200:
            return None
        parsed = res.json()
    except Exception:
        return None

    player = parsed.get("player")
    if not player or not isinstance(player, dict):
        return None
    obj = player.get("pitchingstats")
    if not obj or not isinstance(obj, dict):
        return None
    data = obj.get("season")
    if data is None:
        return None
    if isinstance(data, dict):
        data = [data]
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
#  ALPB Trackman
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_alpb_pitcher_info(fname: str, lname: str) -> dict | None:
    """Look up a pitcher's ALPB ID by name.  Returns a dict or *None*."""
    url = f"{ALPB_BASE_URL}/players"
    try:
        res = _alpb_session.get(url, params={"player_name": f"{lname}, {fname}"})
        res.raise_for_status()
        data = res.json().get("data")
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        player = data[0]
        if player and player.get("is_pitcher"):
            return {
                "player_id": player["player_id"],
                "pitching_hand": player.get("player_pitching_handedness", "Unknown"),
            }
    except Exception:
        pass
    return None


def fetch_alpb_pitches(player_id: str) -> pd.DataFrame | None:
    """Fetch all pitch-by-pitch Trackman data for one pitcher (paginated)."""
    if not player_id:
        return None
    url = f"{ALPB_BASE_URL}/pitches"

    try:
        res = _alpb_session.get(url, params={"pitcher_id": player_id, "page": 1})
        if res.status_code != 200:
            return None
        parsed = res.json()
    except Exception:
        return None

    data = parsed.get("data")
    if not data:
        return None

    all_data: list = list(data)
    total_pages: int = parsed.get("meta", {}).get("total", 1)

    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {
                pool.submit(_fetch_alpb_page, url, player_id, p): p
                for p in range(2, total_pages + 1)
            }
            for fut in as_completed(futures):
                page_data = fut.result()
                if page_data:
                    all_data.extend(page_data)

    return pd.DataFrame(all_data)


# ═══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _find_season(parsed: dict, season_id: str) -> dict | None:
    """Locate the season dict matching *season_id* inside the league JSON."""
    for s in parsed["league"]["season"]:
        if str(s["seasonid"]) == str(season_id):
            return s
    return None


def _safe_str(value) -> str:
    """Coerce any value to a plain string (lists, None → ``""``/``str``)."""
    if value is None:
        return ""
    if isinstance(value, list):
        return str(value)
    return str(value)


def _team_pitchers(team: dict, season_id: str) -> list[dict]:
    """Fetch the pitchers on a single team's roster."""
    tid = team["teamlinkid"]
    tname = team["teamname"]
    url = f"{POINTSTREAK_BASE_URL}/team/roster/{tid}/{season_id}/json"
    try:
        res = _ps_session.get(url)
        if res.status_code != 200:
            return []
        players = res.json().get("league", {}).get("player")
    except Exception:
        return []
    if not players:
        return []
    return [
        {
            "playerid":     _safe_str(p.get("playerid")),
            "playerlinkid": _safe_str(p.get("playerlinkid")),
            "fname":        _safe_str(p.get("fname")),
            "lname":        _safe_str(p.get("lname")),
            "position":     _safe_str(p.get("position")),
            "height":       _safe_str(p.get("height")),
            "weight":       _safe_str(p.get("weight")),
            "birthday":     _safe_str(p.get("birthday")),
            "bats":         _safe_str(p.get("bats")),
            "throws":       _safe_str(p.get("throws")),
            "hometown":     _safe_str(p.get("hometown")),
            "photo":        _safe_str(p.get("photo")),
            "teamlinkid":   tid,
            "teamname":     tname,
        }
        for p in players
        if _safe_str(p.get("position")) == "P"
    ]


def _fetch_alpb_page(url: str, player_id: str, page: int) -> list:
    """Fetch one page of ALPB pitch data (used by the thread pool)."""
    try:
        res = _alpb_session.get(url, params={"pitcher_id": player_id, "page": page})
        if res.status_code == 200:
            return res.json().get("data", [])
    except Exception:
        pass
    return []
