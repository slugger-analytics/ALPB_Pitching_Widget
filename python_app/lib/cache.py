"""
Data-caching service.

Wraps the raw :mod:`python_app.lib.api` module so that every caller gets
transparent, in-memory caching.  Feature modules should import from here
— never directly from ``lib.api``.
"""

from __future__ import annotations

import pandas as pd

from python_app.lib.api import (
    fetch_all_pitchers,
    fetch_alpb_pitcher_info,
    fetch_alpb_pitches,
    fetch_pitching_stats,
)


class DataCache:
    """Loads, caches, and provides all pitcher-related data."""

    def __init__(self) -> None:
        self._pitchers_df: pd.DataFrame = pd.DataFrame()
        self._alpb_ids: dict[str, str | None] = {}
        self._pitch_data: dict[str, list[dict] | None] = {}
        self._season_stats: dict[str, pd.DataFrame | None] = {}

    # ── Roster ────────────────────────────────────────────────────────────

    def load_roster(self) -> None:
        """Fetch and cache the full league roster."""
        self._pitchers_df = fetch_all_pitchers()

    @property
    def pitchers_df(self) -> pd.DataFrame:
        return self._pitchers_df

    @property
    def team_names(self) -> list[str]:
        """Return sorted, non-empty team names from the roster."""
        if self._pitchers_df.empty or "teamname" not in self._pitchers_df.columns:
            return []
        teams = (
            self._pitchers_df["teamname"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        bad = {"", "unknown", "nan", "none", "null", "/"}
        return sorted(t for t in teams.unique().tolist() if t.lower() not in bad)

    @property
    def pitcher_names(self) -> list[str]:
        if self._pitchers_df.empty:
            return []
        names = (
            self._pitchers_df["full_name"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        bad = {"", "unknown", "nan", "none", "null", "/"}
        return [n for n in names.tolist() if n.lower() not in bad]

    def get_players(self, team_name: str | None = None) -> pd.DataFrame:
        """Return roster rows, optionally filtered by *team_name*."""
        if self._pitchers_df.empty:
            return pd.DataFrame()
        if not team_name:
            return self._pitchers_df
        return self._pitchers_df[self._pitchers_df["teamname"] == team_name]

    def get_player_by_linkid(self, playerlinkid: str | None) -> pd.Series | None:
        """Return the roster row for *playerlinkid*, or *None*."""
        if self._pitchers_df.empty or not playerlinkid:
            return None
        rows = self._pitchers_df[
            self._pitchers_df["playerlinkid"].astype(str) == str(playerlinkid)
        ]
        return rows.iloc[0] if not rows.empty else None

    def get_player(self, identifier: str | None) -> pd.Series | None:
        """Return the roster row for a player id (preferred) or full name."""
        if self._pitchers_df.empty or not identifier:
            return None
        by_linkid = self.get_player_by_linkid(identifier)
        if by_linkid is not None:
            return by_linkid
        rows = self._pitchers_df[self._pitchers_df["full_name"] == identifier]
        return rows.iloc[0] if not rows.empty else None

    # ── Season stats ──────────────────────────────────────────────────────

    def get_season_stats(self, playerlinkid: str) -> pd.DataFrame | None:
        """Return cached season stats, fetching on first access."""
        if playerlinkid in self._season_stats:
            return self._season_stats[playerlinkid]
        try:
            stats = fetch_pitching_stats(playerlinkid)
        except Exception:
            stats = None
        self._season_stats[playerlinkid] = stats
        return stats

    # ── ALPB player ID ────────────────────────────────────────────────────

    def get_alpb_id(self, playerlinkid: str | None) -> str | None:
        """Return the ALPB Trackman player ID for a Pointstreak playerlinkid."""
        if not playerlinkid:
            return None
        key = str(playerlinkid)
        if key in self._alpb_ids:
            return self._alpb_ids[key]

        player = self.get_player_by_linkid(key)
        if player is None:
            return None
        result = fetch_alpb_pitcher_info(player["fname"], player["lname"])
        pid = result["player_id"] if result else None
        self._alpb_ids[key] = pid
        return pid

    # ── Pitch-by-pitch data ───────────────────────────────────────────────

    def get_pitch_data(self, player_id: str) -> list[dict] | None:
        """Return raw pitch records for *player_id*, fetching on first access."""
        if not player_id:
            return None
        if player_id in self._pitch_data:
            return self._pitch_data[player_id]
        df = fetch_alpb_pitches(player_id)
        if df is None or df.empty:
            self._pitch_data[player_id] = None
            return None
        records = df.to_dict("records")
        self._pitch_data[player_id] = records
        return records


# Module-level singleton used by all features
cache = DataCache()
