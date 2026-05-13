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
    DATA_SOURCE,
    DEFAULT_SEASON_ID,
    EXCLUDED_TEAMS,
    ISCORE_BASE_URL,
    ISCORE_LEAGUE_GUID,
    ISCORE_SEASON_GUID,
    ISCORE_SEASON_NAME,
    LEAGUE_ID,
    MAX_WORKERS,
    POINTSTREAK_API_KEY,
    POINTSTREAK_BASE_URL,
)
from python_app.lib.conditioning import clean_pitcher_roster
from python_app.lib.sample_data import (
    load_sample_pitches,
    load_sample_pitcher_info,
    load_sample_pitchers,
    load_sample_pitching_stats,
)

# Persistent HTTP sessions for connection reuse
_ps_session = requests.Session()
_ps_session.headers.update({"apikey": POINTSTREAK_API_KEY})

_alpb_session = requests.Session()
_alpb_session.headers.update({"x-api-key": ALPB_API_KEY})

_iscore_session = requests.Session()  # no auth required

_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


# ═══════════════════════════════════════════════════════════════════════════════
#  Pointstreak
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_all_pitchers(season_id: str = DEFAULT_SEASON_ID) -> pd.DataFrame:
    """Fetch every pitcher across all ALPB teams for *season_id*."""
    if DATA_SOURCE == "sample":
        return load_sample_pitchers()

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

    return clean_pitcher_roster(pd.DataFrame(all_pitchers), EXCLUDED_TEAMS)


def fetch_pitching_stats(
    playerlinkid: str,
    season_id: str = DEFAULT_SEASON_ID,
) -> pd.DataFrame | None:
    """Fetch aggregated season pitching stats for one player."""
    if DATA_SOURCE == "sample":
        return load_sample_pitching_stats(playerlinkid)

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
    stat_order = ["name", "teamname", "gp", "gs", "w", "l", "era", "er", "h", "bb", "so", "ip", "sv"]
    cols = [c for c in stat_order if c in df.columns]
    return df[cols]


# ═══════════════════════════════════════════════════════════════════════════════
#  ALPB Trackman
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_alpb_pitcher_info(fname: str, lname: str) -> dict | None:
    """Look up a pitcher's ALPB ID by name.  Returns a dict or *None*."""
    if DATA_SOURCE == "sample":
        return load_sample_pitcher_info(fname, lname)

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


# ═══════════════════════════════════════════════════════════════════════════════
#  iScore
# ═══════════════════════════════════════════════════════════════════════════════

# Stat key aliases from iScore → our canonical names
_ISCORE_STAT_ALIASES: dict[str, str] = {
    "strikeouts": "so",
    "k": "so",
    "walks": "bb",
    "innings_pitched": "ip",
    "earned_runs": "er",
    "hits_allowed": "h",
    "games_played": "gp",
    "games_started": "gs",
    "saves": "sv",
    "wins": "w",
    "losses": "l",
    "earned_run_average": "era",
}

_PITCHER_POSITION_TOKENS: frozenset[str] = frozenset(
    {"p", "sp", "rp", "cp", "cl", "pitcher", "pitchers",
     "starting pitcher", "relief pitcher", "closer"}
)


def fetch_iscore_teams(league_guid: str) -> list[dict]:
    """Fetch all teams in an iScore league."""
    url = f"{ISCORE_BASE_URL}/public/leagues/{league_guid}/teams"
    try:
        res = _iscore_session.get(url, timeout=15)
        res.raise_for_status()
        return res.json() or []
    except Exception:
        return []


def _iscore_team_pitchers(team: dict) -> list[dict]:
    """Fetch pitcher rows from one iScore team roster."""
    tid = team["guid"]
    tname = team["name"]
    url = f"{ISCORE_BASE_URL}/public/teams/{tid}/players"
    try:
        res = _iscore_session.get(url, timeout=15)
        if res.status_code != 200:
            return []
        players = res.json()
    except Exception:
        return []
    if not players:
        return []

    result: list[dict] = []
    for p in players:
        if not p.get("active", True):
            continue
        pg = p.get("positionGroup") or {}
        pos_name = str(pg.get("name", "")).strip()
        if pos_name.lower() not in _PITCHER_POSITION_TOKENS:
            continue

        full = " ".join(str(p.get("name", "")).split())
        parts = full.split(" ", 1)
        fname = parts[0] if parts else ""
        lname = parts[1] if len(parts) > 1 else ""

        result.append({
            "iscore_guid":  str(p.get("guid", "")),
            "fname":        fname,
            "lname":        lname,
            "full_name":    full,
            "teamname":     tname,
            "bats":         _safe_str(p.get("bats")),
            "throws":       _safe_str(p.get("throwsHand")),
            "height":       _safe_str(p.get("height")),
            "weight":       _safe_str(p.get("weight")),
            "number":       _safe_str(p.get("number")),
            "position":     pos_name,
            # PS-sourced fields filled in after name-match merge
            "playerlinkid": "",
            "playerid":     "",
            "photo":        "",
            "hometown":     "",
            "birthday":     "",
        })
    return result


def fetch_iscore_pitchers(league_guid: str) -> pd.DataFrame:
    """Fetch all pitchers across all iScore teams for the league."""
    teams = fetch_iscore_teams(league_guid)
    if not teams:
        return pd.DataFrame()

    all_pitchers: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_iscore_team_pitchers, t): t for t in teams}
        for fut in as_completed(futures):
            try:
                all_pitchers.extend(fut.result())
            except Exception:
                continue

    if not all_pitchers:
        return pd.DataFrame()

    df = pd.DataFrame(all_pitchers)
    df = df[~df["teamname"].isin(EXCLUDED_TEAMS)]

    bad = {"", "unknown", "nan", "none", "null", "/"}
    df = df[
        ~df["fname"].str.lower().isin(bad)
        & ~df["lname"].str.lower().isin(bad)
    ]
    return df.sort_values("lname").reset_index(drop=True)


def merge_iscore_with_ps(iscore_df: pd.DataFrame, ps_df: pd.DataFrame) -> pd.DataFrame:
    """Enrich iScore roster with Pointstreak fields matched by normalized full name.

    Team names are the same between systems; only the player IDs differ.
    Players new to the league simply get empty PS fields.
    """
    if ps_df.empty or iscore_df.empty:
        return iscore_df

    ps_cols = ["playerlinkid", "playerid", "photo", "hometown", "birthday"]

    # Build PS lookup keyed by normalized "fname lname"
    ps_name_key = (ps_df["fname"] + " " + ps_df["lname"]).apply(_normalize_name)
    ps_enrich = (
        ps_df.assign(_name_key=ps_name_key)[["_name_key"] + ps_cols]
        .drop_duplicates("_name_key")
    )

    # Drop the empty placeholder columns from the iScore df before merging
    iscore_copy = iscore_df.drop(columns=ps_cols, errors="ignore").copy()
    iscore_copy["_name_key"] = iscore_copy["full_name"].apply(_normalize_name)

    merged = iscore_copy.merge(ps_enrich, on="_name_key", how="left")
    for col in ps_cols:
        if col not in merged.columns:
            merged[col] = ""
        merged[col] = merged[col].fillna("").astype(str)

    merged.drop(columns=["_name_key"], inplace=True, errors="ignore")
    return merged.reset_index(drop=True)


def fetch_all_pitchers_combined(season_id: str = DEFAULT_SEASON_ID) -> pd.DataFrame:
    """Fetch pitchers from iScore (authoritative roster) + Pointstreak (for IDs/photos).

    Falls back to Pointstreak-only when ISCORE_LEAGUE_GUID is not configured.
    """
    ps_df = fetch_all_pitchers(season_id)

    if not ISCORE_LEAGUE_GUID:
        # iScore not configured — use PS roster with iscore_guid aliased to playerlinkid
        if not ps_df.empty:
            ps_df = ps_df.copy()
            ps_df["iscore_guid"] = ps_df["playerlinkid"].astype(str)
        return ps_df

    iscore_df = fetch_iscore_pitchers(ISCORE_LEAGUE_GUID)
    if iscore_df.empty:
        # iScore returned nothing — fall back to PS
        if not ps_df.empty:
            ps_df = ps_df.copy()
            ps_df["iscore_guid"] = ps_df["playerlinkid"].astype(str)
        return ps_df

    return merge_iscore_with_ps(iscore_df, ps_df)


def fetch_iscore_player_stats(player_guid: str) -> pd.DataFrame | None:
    """Fetch season pitching stats for one iScore player."""
    if not player_guid:
        return None
    url = f"{ISCORE_BASE_URL}/player-stats"
    params: dict = {"playerId": player_guid}
    if ISCORE_SEASON_GUID:
        params["seasonId"] = ISCORE_SEASON_GUID
    try:
        res = _iscore_session.get(url, params=params, timeout=15)
        if res.status_code != 200:
            return None
        data = res.json()
    except Exception:
        return None

    if not isinstance(data, list) or not data:
        return None

    entry = next(
        (e for e in data if str(e.get("playerId", "")).lower() == player_guid.lower()),
        data[0],
    )

    # Response shape: stats.pitching.overall + stats.pitching.overall.RATES
    raw_stats = entry.get("stats") or {}
    pitching = raw_stats.get("pitching") or {}
    overall = pitching.get("overall") or {}
    rates = overall.get("RATES") or {}

    if not overall:
        return None

    outs = overall.get("OUTS_PITCHED", 0) or 0
    ip_full = int(outs) // 3
    ip_rem  = int(outs) % 3
    ip = float(f"{ip_full}.{ip_rem}") if ip_rem else float(ip_full)

    fname = str(entry.get("firstName", "")).strip()
    lname = str(entry.get("lastName", "")).strip()

    normalized: dict = {
        "name": ISCORE_SEASON_NAME,
        "gs":   overall.get("GS"),
        "sv":   overall.get("SV"),
        "er":   overall.get("ER"),
        "h":    overall.get("H"),
        "bb":   overall.get("BB"),
        "so":   overall.get("SO"),
        "ip":   ip,
        "era":  rates.get("ERA"),
    }

    stat_order = ["name", "teamname", "gs", "era", "er", "h", "bb", "so", "ip", "sv"]
    df = pd.DataFrame([normalized])
    cols = [c for c in stat_order if c in df.columns]
    return df[cols] if cols else df


def fetch_alpb_pitches(player_id: str) -> pd.DataFrame | None:
    """Fetch all pitch-by-pitch Trackman data for one pitcher (paginated)."""
    if not player_id:
        return None
    if DATA_SOURCE == "sample":
        return load_sample_pitches(player_id)

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
