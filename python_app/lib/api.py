"""
API clients for Pointstreak and ALPB Trackman.

All external HTTP calls live here.  No caching — that responsibility
belongs to :mod:`python_app.lib.cache`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import unicodedata

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

_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


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

    # Drop rows without a usable player name so the dropdown never shows
    # placeholders like "Unknown" / empty names.
    df["fname"] = df["fname"].fillna("").astype(str).str.strip()
    df["lname"] = df["lname"].fillna("").astype(str).str.strip()
    bad_name_tokens = {"", "unknown", "nan", "none", "null", "/"}
    valid_name_mask = (
        ~df["fname"].str.lower().isin(bad_name_tokens)
        & ~df["lname"].str.lower().isin(bad_name_tokens)
    )
    df = df[valid_name_mask]

    df = df.sort_values("lname").reset_index(drop=True)
    df["full_name"] = (df["fname"] + " " + df["lname"]).str.strip()
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
    df = pd.DataFrame(data)
    stat_order = ["gp", "gs", "w", "l", "sv", "h", "bb", "so", "ip", "er", "era"]
    cols = [c for c in stat_order if c in df.columns] + [c for c in df.columns if c not in stat_order]
    return df[cols]


# ═══════════════════════════════════════════════════════════════════════════════
#  ALPB Trackman
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_alpb_pitcher_info(fname: str, lname: str) -> dict | None:
    """Look up a pitcher's ALPB ID by name.  Returns a dict or *None*."""
    url = f"{ALPB_BASE_URL}/players"
    for query in _alpb_query_candidates(fname, lname):
        try:
            res = _alpb_session.get(url, params={"player_name": query})
            res.raise_for_status()
            data = res.json().get("data")
            if not isinstance(data, list) or not data:
                continue
            player = _select_pitcher_match(data, fname, lname)
            if player and player.get("player_id"):
                return {
                    "player_id": player["player_id"],
                    "pitching_hand": player.get("player_pitching_handedness", "Unknown"),
                }
        except Exception:
            continue
    return None


def _alpb_query_candidates(fname: str, lname: str) -> list[str]:
    """Return de-duplicated query variants for ALPB `/players`."""
    first = str(fname or "").strip()
    last = str(lname or "").strip()
    if not first or not last:
        return []

    first_ascii = _ascii_fold(first)
    last_ascii = _ascii_fold(last)
    last_no_suffix = _strip_suffix_raw(last)
    last_no_suffix_ascii = _ascii_fold(last_no_suffix)

    queries: list[str] = []
    seen: set[str] = set()

    def _add(q: str) -> None:
        token = q.strip()
        if not token:
            return
        key = token.casefold()
        if key in seen:
            return
        seen.add(key)
        queries.append(token)

    _add(f"{last}, {first}")
    _add(f"{last_ascii}, {first_ascii}")
    if last_no_suffix:
        _add(f"{last_no_suffix}, {first}")
    if last_no_suffix_ascii:
        _add(f"{last_no_suffix_ascii}, {first_ascii}")

    return queries


def _select_pitcher_match(players: list[dict], fname: str, lname: str) -> dict | None:
    """Choose the best pitcher candidate from ALPB `/players` response."""
    pitchers = [p for p in players if isinstance(p, dict) and p.get("is_pitcher")]
    if not pitchers:
        return None

    target_first = _normalize_name(fname).split(" ")[0]
    target_last = _strip_suffix_norm(_normalize_name(lname))

    for player in pitchers:
        first_name, last_name = _player_name_parts(player)
        first_norm = _normalize_name(first_name).split(" ")[0]
        last_norm = _strip_suffix_norm(_normalize_name(last_name))
        if first_norm == target_first and last_norm == target_last:
            return player

    if len(pitchers) == 1:
        return pitchers[0]
    return None


def _player_name_parts(player: dict) -> tuple[str, str]:
    """Extract first/last name from ALPB player payload fields."""
    first = str(
        player.get("player_first_name")
        or player.get("first_name")
        or player.get("fname")
        or ""
    ).strip()
    last = str(
        player.get("player_last_name")
        or player.get("last_name")
        or player.get("lname")
        or ""
    ).strip()

    if first and last:
        return first, last

    full = str(player.get("player_name") or player.get("full_name") or "").strip()
    if "," in full:
        raw_last, raw_first = [part.strip() for part in full.split(",", 1)]
        return raw_first or first, raw_last or last
    parts = [part for part in full.split(" ") if part]
    if parts and not first:
        first = parts[0]
    if len(parts) > 1 and not last:
        last = " ".join(parts[1:])
    return first, last


def _ascii_fold(value: str) -> str:
    """Convert accented unicode text to plain ASCII."""
    text = str(value or "")
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _normalize_name(value: str) -> str:
    """Case-insensitive / punctuation-insensitive normalization for names."""
    text = _ascii_fold(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_suffix_norm(value: str) -> str:
    """Remove common baseball suffix tokens from normalized names."""
    tokens = value.split()
    while tokens and tokens[-1] in _NAME_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _strip_suffix_raw(value: str) -> str:
    """Remove common suffix tokens while preserving raw display casing."""
    tokens = [t for t in str(value or "").strip().split(" ") if t]
    while tokens:
        tail = _normalize_name(tokens[-1]).replace(" ", "")
        if tail in _NAME_SUFFIXES:
            tokens.pop()
            continue
        break
    return " ".join(tokens)


def fetch_alpb_pitches(player_id: str) -> pd.DataFrame | None:
    """Fetch all pitch-by-pitch Trackman data for one pitcher (paginated)."""
    if not player_id:
        return None
    url = f"{ALPB_BASE_URL}/pitches"

    # `/pitches` pagination metadata is inconsistent across API versions.
    # Pull sequentially until an empty page to avoid silent truncation.
    all_data: list[dict] = []
    page = 1
    while True:
        page_data = _fetch_alpb_page(url, player_id, page)
        if not page_data:
            break
        all_data.extend(page_data)
        page += 1

    if not all_data:
        return None
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
