"""
Pointstreak API client.

Fetches pitcher rosters and season statistics from the Pointstreak Baseball API.
Equivalent to getPointstreakPlayers.R and getSeasonStats.R.
"""

import requests
import pandas as pd

POINTSTREAK_API_KEY = "vIpQsngDfc6Y7WVgAcTt"
DEFAULT_SEASON_ID = "34104"
EXCLUDED_TEAMS = {"Staten Island Ferry Hawks", "Long Island Black Sox"}


def get_all_pitchers(season_id=DEFAULT_SEASON_ID):
    """
    Fetch all pitchers from every ALPB team for the given season.

    Returns a DataFrame with columns:
        playerid, playerlinkid, fname, lname, position, height, weight,
        birthday, bats, throws, hometown, photo, teamlinkid, teamname, full_name
    """
    # Get league structure to find all teams
    url = "https://api.pointstreak.com/baseball/league/structure/174/json"
    headers = {"apikey": POINTSTREAK_API_KEY}
    params = {"seasonid": season_id}

    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    parsed = res.json()

    # Find the matching season
    season = None
    for s in parsed["league"]["season"]:
        if s["seasonid"] == season_id:
            season = s
            break

    if season is None:
        return pd.DataFrame()

    # Extract all teams from all divisions
    teams = []
    for div in season["division"]:
        teams.extend(div["team"])

    # Fetch roster for each team and collect pitchers
    all_pitchers = []
    for team in teams:
        team_pitchers = _get_pitchers_for_team(team, season_id)
        all_pitchers.extend(team_pitchers)

    if not all_pitchers:
        return pd.DataFrame()

    df = pd.DataFrame(all_pitchers)
    # Filter excluded teams
    df = df[~df["teamname"].isin(EXCLUDED_TEAMS)]
    # Sort by last name
    df = df.sort_values("lname").reset_index(drop=True)
    # Add full name
    df["full_name"] = df["fname"] + " " + df["lname"]
    return df


def _get_pitchers_for_team(team, season_id):
    """Fetch the roster for a single team and return pitcher records."""
    teamlinkid = team["teamlinkid"]
    teamname = team["teamname"]

    url = f"https://api.pointstreak.com/baseball/team/roster/{teamlinkid}/{season_id}/json"
    headers = {"apikey": POINTSTREAK_API_KEY}

    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return []
        parsed = res.json()
    except Exception:
        return []

    players = parsed.get("league", {}).get("player")
    if players is None:
        return []

    pitchers = []
    for p in players:
        if _safe(p.get("position")) != "P":
            continue
        pitchers.append({
            "playerid": _safe(p.get("playerid")),
            "playerlinkid": _safe(p.get("playerlinkid")),
            "fname": _safe(p.get("fname")),
            "lname": _safe(p.get("lname")),
            "position": _safe(p.get("position")),
            "height": _safe(p.get("height")),
            "weight": _safe(p.get("weight")),
            "birthday": _safe(p.get("birthday")),
            "bats": _safe(p.get("bats")),
            "throws": _safe(p.get("throws")),
            "hometown": _safe(p.get("hometown")),
            "photo": _safe(p.get("photo")),
            "teamlinkid": teamlinkid,
            "teamname": teamname,
        })
    return pitchers


def _safe(value):
    """Safely extract a field value, converting None or lists to string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return str(value)
    return str(value)


def get_pitching_stats(playerlinkid, season_id=DEFAULT_SEASON_ID):
    """
    Fetch aggregated season pitching statistics for a player.

    Returns a DataFrame with season stats columns (ERA, WHIP, etc.),
    or None if no data found.
    """
    url = f"https://api.pointstreak.com/baseball/player/stats/{playerlinkid}/{season_id}/json"
    headers = {"apikey": POINTSTREAK_API_KEY}

    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return None
        parsed = res.json()
    except Exception:
        return None

    pitching_stats = (
        parsed.get("player", {})
        .get("pitchingstats", {})
        .get("season")
    )
    if pitching_stats is None:
        return None

    df = pd.DataFrame(pitching_stats)
    return df
