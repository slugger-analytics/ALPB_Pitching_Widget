"""
Data-caching service.

Wraps the raw :mod:`python_app.lib.api` module so that every caller gets
transparent, in-memory caching.  Feature modules should import from here
— never directly from ``lib.api``.
"""

from __future__ import annotations

import threading
import time

import pandas as pd

from python_app.config import NEGATIVE_ID_TTL_SECONDS, ROSTER_TTL_SECONDS
from python_app.lib.api import (
    fetch_all_pitchers_combined,
    fetch_alpb_pitcher_info,
    fetch_alpb_pitches,
    fetch_iscore_player_stats,
)


class DataCache:
    """Loads, caches, and provides all pitcher-related data."""

    def __init__(self) -> None:
        self._pitchers_df: pd.DataFrame = pd.DataFrame()
        self._roster_loaded_at: float | None = None
        # Each entry is (player_id_or_None, cached_at_monotonic). Positive ids
        # persist; negative (None) entries expire after NEGATIVE_ID_TTL_SECONDS.
        self._alpb_ids: dict[str, tuple[str | None, float]] = {}
        self._pitch_data: dict[str, list[dict] | None] = {}
        self._season_stats: dict[str, pd.DataFrame | None] = {}
        self._roster_lock = threading.Lock()
        self._roster_refreshing = False

    # ── Roster ────────────────────────────────────────────────────────────

    def load_roster(self) -> None:
        """Fetch the full league roster from iScore and atomically swap it in.

        The new DataFrame is built fully, then the served roster is replaced in a
        single assignment. On any fetch failure (exception or empty result) the
        previous roster is kept — a transient API blip must never serve an empty
        roster to users.
        """
        try:
            new_df = fetch_all_pitchers_combined()
        except Exception:
            return  # transient failure — keep the previous roster
        if new_df is None or new_df.empty:
            return  # never serve empty on a transient/empty fetch
        self._pitchers_df = new_df            # atomic swap (single assignment)
        self._roster_loaded_at = time.monotonic()

    def roster_is_stale(self) -> bool:
        """True when the roster has never loaded or has aged past its TTL."""
        if self._roster_loaded_at is None:
            return True
        return (time.monotonic() - self._roster_loaded_at) >= ROSTER_TTL_SECONDS

    def refresh_roster_if_stale(self) -> bool:
        """Reload the roster if it is stale and no refresh is already in flight.

        Returns True if this call performed the (re)load, False if it was skipped
        because the roster is still fresh or another thread is already
        refreshing (the lock/in-flight flag stops overlapping refetches).
        """
        if not self.roster_is_stale():
            return False
        with self._roster_lock:
            if self._roster_refreshing or not self.roster_is_stale():
                return False
            self._roster_refreshing = True
        try:
            self.load_roster()
        finally:
            with self._roster_lock:
                self._roster_refreshing = False
        return True

    @property
    def pitchers_df(self) -> pd.DataFrame:
        return self._pitchers_df

    @property
    def team_names(self) -> list[str]:
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

    def get_player_by_guid(self, iscore_guid: str | None) -> pd.Series | None:
        """Return the roster row for *iscore_guid*, or *None*."""
        if self._pitchers_df.empty or not iscore_guid:
            return None
        if "iscore_guid" not in self._pitchers_df.columns:
            return None
        rows = self._pitchers_df[
            self._pitchers_df["iscore_guid"].astype(str) == str(iscore_guid)
        ]
        return rows.iloc[0] if not rows.empty else None

    def get_player(self, identifier: str | None) -> pd.Series | None:
        """Return the roster row for a player (by iscore_guid or full name)."""
        if self._pitchers_df.empty or not identifier:
            return None
        by_guid = self.get_player_by_guid(identifier)
        if by_guid is not None:
            return by_guid
        rows = self._pitchers_df[self._pitchers_df["full_name"] == identifier]
        return rows.iloc[0] if not rows.empty else None

    # ── Season stats ──────────────────────────────────────────────────────

    def get_season_stats(self, iscore_guid: str) -> pd.DataFrame | None:
        """Return cached season stats from iScore."""
        if iscore_guid in self._season_stats:
            return self._season_stats[iscore_guid]

        player = self.get_player(iscore_guid)
        combined: pd.DataFrame | None = None

        if player is not None and iscore_guid:
            try:
                combined = fetch_iscore_player_stats(iscore_guid)
                if combined is not None:
                    combined["teamname"] = str(player.get("teamname", ""))
            except Exception:
                combined = None

        if combined is not None:
            col_order = ["name", "teamname", "gp", "gs", "w", "l", "era", "er", "h", "bb", "so", "ip", "sv"]
            ordered = [c for c in col_order if c in combined.columns]
            combined = combined[ordered].rename(columns={"name": "season"})

            if "era" in combined.columns:
                combined["era"] = (
                    pd.to_numeric(combined["era"], errors="coerce")
                    .round(2)
                    .where(pd.notna(pd.to_numeric(combined["era"], errors="coerce")), combined["era"])
                )
            combined = combined.fillna("-")

        self._season_stats[iscore_guid] = combined
        return combined

    # ── ALPB player ID ────────────────────────────────────────────────────

    def get_alpb_id(self, iscore_guid: str | None) -> str | None:
        """Return the ALPB Trackman player ID for an iscore_guid.

        Positive results are cached for the process lifetime; negative
        (not-found) results expire after ``NEGATIVE_ID_TTL_SECONDS`` so a pitcher
        who only later appears in the ALPB feed is eventually resolved.
        """
        if not iscore_guid:
            return None
        key = str(iscore_guid)
        cached = self._alpb_ids.get(key)
        if cached is not None:
            value, cached_at = cached
            if value is not None:
                return value  # positive entries persist
            if (time.monotonic() - cached_at) < NEGATIVE_ID_TTL_SECONDS:
                return None   # negative entry still within its TTL
            # negative entry expired — fall through and retry the lookup

        player = self.get_player_by_guid(key)
        if player is None:
            self._alpb_ids[key] = (None, time.monotonic())
            return None
        result = fetch_alpb_pitcher_info(player["fname"], player["lname"])
        pid = result["player_id"] if result else None
        self._alpb_ids[key] = (pid, time.monotonic())
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
