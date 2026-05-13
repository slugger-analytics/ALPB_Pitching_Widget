"""
Data-caching service.

Wraps the raw :mod:`python_app.lib.api` module so that every caller gets
transparent, in-memory caching.  Feature modules should import from here
— never directly from ``lib.api``.

The primary player key throughout is ``iscore_guid`` (iScore GUID).
When iScore is not configured the field is aliased to the Pointstreak
``playerlinkid`` so the rest of the app is unaffected.
"""

from __future__ import annotations

import pandas as pd

from python_app.lib.api import (
    fetch_all_pitchers_combined,
    fetch_alpb_pitcher_info,
    fetch_alpb_pitches,
    fetch_iscore_player_stats,
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
        """Fetch and cache the full league roster from iScore + Pointstreak."""
        self._pitchers_df = fetch_all_pitchers_combined()

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
        """Return cached combined season stats (iScore + Pointstreak)."""
        if iscore_guid in self._season_stats:
            return self._season_stats[iscore_guid]

        player = self.get_player(iscore_guid)

        # iScore stats
        iscore_stats: pd.DataFrame | None = None
        # Skip iScore lookup for PS-alias GUIDs (fallback mode)
        if player is not None and iscore_guid and not iscore_guid.isdigit():
            try:
                iscore_stats = fetch_iscore_player_stats(iscore_guid)
                if iscore_stats is not None:
                    iscore_stats["teamname"] = str(player.get("teamname", ""))
            except Exception:
                iscore_stats = None

        # Pointstreak stats
        ps_stats: pd.DataFrame | None = None
        ps_linkid = str(player["playerlinkid"]).strip() if player is not None else ""
        bad = {"", "nan", "none", "null"}
        if ps_linkid.lower() not in bad:
            try:
                ps_stats = fetch_pitching_stats(ps_linkid)
            except Exception:
                ps_stats = None

        # Combine — iScore rows first, then PS rows; no recalculation
        if iscore_stats is not None and ps_stats is not None:
            combined: pd.DataFrame | None = pd.concat(
                [iscore_stats, ps_stats], ignore_index=True
            )
        elif iscore_stats is not None:
            combined = iscore_stats
        elif ps_stats is not None:
            combined = ps_stats
        else:
            combined = None

        if combined is not None:
            for col in ("gp", "w", "l"):
                if col not in combined.columns:
                    combined[col] = "-"
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
        """Return the ALPB Trackman player ID for an iscore_guid."""
        if not iscore_guid:
            return None
        key = str(iscore_guid)
        if key in self._alpb_ids:
            return self._alpb_ids[key]

        player = self.get_player_by_guid(key)
        if player is None:
            self._alpb_ids[key] = None
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
