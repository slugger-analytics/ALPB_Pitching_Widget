"""
Data-conditioning helpers shared by live and sample data sources.

These functions define the repo's lightweight preprocessing contract:
normalize types, drop unusable rows, and derive the display-ready fields
used by the Dash app.
"""

from __future__ import annotations

import pandas as pd

ROSTER_COLUMNS: list[str] = [
    "playerid",
    "playerlinkid",
    "fname",
    "lname",
    "position",
    "height",
    "weight",
    "birthday",
    "bats",
    "throws",
    "hometown",
    "photo",
    "teamlinkid",
    "teamname",
]


def clean_pitcher_roster(
    df: pd.DataFrame | None,
    excluded_teams: set[str] | None = None,
) -> pd.DataFrame:
    """Normalize roster records and derive ``full_name`` for UI use."""
    if df is None or df.empty:
        return pd.DataFrame(columns=ROSTER_COLUMNS + ["full_name"])

    cleaned = df.copy()
    for column in ROSTER_COLUMNS:
        if column not in cleaned.columns:
            cleaned[column] = ""
        cleaned[column] = cleaned[column].fillna("").astype(str).str.strip()

    if excluded_teams:
        cleaned = cleaned[~cleaned["teamname"].isin(excluded_teams)]

    bad_name_tokens = {"", "unknown", "nan", "none", "null", "/"}
    valid_name_mask = (
        ~cleaned["fname"].str.lower().isin(bad_name_tokens)
        & ~cleaned["lname"].str.lower().isin(bad_name_tokens)
    )
    cleaned = cleaned[valid_name_mask].copy()
    cleaned["full_name"] = (cleaned["fname"] + " " + cleaned["lname"]).str.strip()

    return cleaned.sort_values("lname").reset_index(drop=True)


def filter_season_stats(
    df: pd.DataFrame | None,
    playerlinkid: str,
) -> pd.DataFrame | None:
    """Return one player's season-stat rows, minus lookup columns."""
    if df is None or df.empty:
        return None

    key = str(playerlinkid or "").strip()
    if not key or "playerlinkid" not in df.columns:
        return None

    filtered = df[df["playerlinkid"].astype(str).str.strip() == key].copy()
    if filtered.empty:
        return None

    return filtered.drop(columns=["playerlinkid"]).reset_index(drop=True)


def filter_pitch_data(
    df: pd.DataFrame | None,
    player_id: str,
) -> pd.DataFrame | None:
    """Return pitch-level rows for one player ID."""
    if df is None or df.empty:
        return None

    key = str(player_id or "").strip()
    if not key or "player_id" not in df.columns:
        return None

    filtered = df[df["player_id"].astype(str).str.strip() == key].copy()
    if filtered.empty:
        return None

    return filtered.reset_index(drop=True)
