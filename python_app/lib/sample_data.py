"""
Sample-data provider for reviewer-friendly offline runs.

The sample files mimic the minimal schema required by the live app so
external reviewers can boot the dashboard without private API access.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from python_app.config import EXCLUDED_TEAMS, SAMPLE_DATA_DIR
from python_app.lib.conditioning import (
    clean_pitcher_roster,
    filter_pitch_data,
    filter_season_stats,
)


def _read_csv(filename: str) -> pd.DataFrame:
    path = Path(SAMPLE_DATA_DIR) / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Sample data file not found: {path}. "
            "Check SAMPLE_DATA_DIR or restore the bundled sample files."
        )
    return pd.read_csv(path)


def load_sample_pitchers() -> pd.DataFrame:
    """Load and clean the public sample pitcher roster."""
    raw = _read_csv("pitchers.csv")
    return clean_pitcher_roster(raw, EXCLUDED_TEAMS)


def load_sample_pitching_stats(playerlinkid: str) -> pd.DataFrame | None:
    """Load one player's sample season stats."""
    raw = _read_csv("season_stats.csv")
    return filter_season_stats(raw, playerlinkid)


def load_sample_pitcher_info(fname: str, lname: str) -> dict | None:
    """Resolve a sample ALPB player lookup by first/last name."""
    raw = _read_csv("alpb_lookup.csv")
    if raw.empty:
        return None

    first = str(fname or "").strip().casefold()
    last = str(lname or "").strip().casefold()
    match = raw[
        raw["fname"].astype(str).str.strip().str.casefold().eq(first)
        & raw["lname"].astype(str).str.strip().str.casefold().eq(last)
    ]
    if match.empty:
        return None

    row = match.iloc[0]
    return {
        "player_id": str(row.get("player_id", "")).strip(),
        "pitching_hand": str(row.get("pitching_hand", "Unknown")).strip() or "Unknown",
    }


def load_sample_pitches(player_id: str) -> pd.DataFrame | None:
    """Load pitch-level sample records for one ALPB player ID."""
    raw = _read_csv("pitches.csv")
    return filter_pitch_data(raw, player_id)
