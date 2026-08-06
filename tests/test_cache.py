"""Tests for periodic roster + cache refresh (P1).

A Fargate container lives for days, so the roster, negative ALPB-id lookups,
pitch data and season stats must expire and refresh in place — otherwise newly
signed pitchers never appear and today's pitches never load without a container
restart. A transient API failure must never wipe the already-served data.
"""

from __future__ import annotations

import threading
import time

import pandas as pd

from python_app.config import (
    NEGATIVE_ID_TTL_SECONDS,
    NEGATIVE_PITCH_DATA_TTL_SECONDS,
    PITCH_DATA_TTL_SECONDS,
    REFETCH_BACKOFF_SECONDS,
    ROSTER_TTL_SECONDS,
    SEASON_STATS_TTL_SECONDS,
)
from python_app.lib.cache import DataCache


def _roster_df(guid: str = "g1", fname: str = "Alex", lname: str = "Ace") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "iscore_guid": [guid],
            "fname": [fname],
            "lname": [lname],
            "full_name": [f"{fname} {lname}"],
            "teamname": ["Test Team"],
        }
    )


# ── Roster staleness / refresh ────────────────────────────────────────────

def test_stale_roster_triggers_refetch(monkeypatch):
    calls = []

    def fake_fetch():
        calls.append(1)
        return _roster_df()

    monkeypatch.setattr("python_app.lib.cache.fetch_all_pitchers_combined", fake_fetch)

    dc = DataCache()
    dc.load_roster()
    assert len(calls) == 1
    assert not dc.roster_is_stale()

    # Age the roster past its TTL.
    dc._roster_loaded_at = time.monotonic() - (ROSTER_TTL_SECONDS + 1)
    assert dc.roster_is_stale()

    assert dc.refresh_roster_if_stale() is True
    assert len(calls) == 2


def test_fresh_roster_not_refetched(monkeypatch):
    calls = []

    def fake_fetch():
        calls.append(1)
        return _roster_df()

    monkeypatch.setattr("python_app.lib.cache.fetch_all_pitchers_combined", fake_fetch)

    dc = DataCache()
    dc.load_roster()
    assert len(calls) == 1
    assert not dc.roster_is_stale()

    assert dc.refresh_roster_if_stale() is False
    assert len(calls) == 1


def test_failed_refetch_keeps_previous_df(monkeypatch):
    monkeypatch.setattr(
        "python_app.lib.cache.fetch_all_pitchers_combined", lambda: _roster_df()
    )
    dc = DataCache()
    dc.load_roster()
    assert len(dc.pitchers_df) == 1

    # (a) Exception on refetch → previous roster retained.
    def boom():
        raise RuntimeError("iScore unreachable")

    monkeypatch.setattr("python_app.lib.cache.fetch_all_pitchers_combined", boom)
    dc._roster_loaded_at = time.monotonic() - (ROSTER_TTL_SECONDS + 1)
    dc.refresh_roster_if_stale()
    assert len(dc.pitchers_df) == 1  # never served empty

    # (b) Empty return on refetch → previous roster retained.
    monkeypatch.setattr(
        "python_app.lib.cache.fetch_all_pitchers_combined", lambda: pd.DataFrame()
    )
    dc._roster_loaded_at = time.monotonic() - (ROSTER_TTL_SECONDS + 1)
    dc.refresh_roster_if_stale()
    assert len(dc.pitchers_df) == 1


# ── ALPB id caching (positive persists, negative expires) ─────────────────

def test_positive_alpb_id_persists(monkeypatch):
    calls = []

    def fake_info(fname, lname):
        calls.append((fname, lname))
        return {"player_id": "555"}

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitcher_info", fake_info)

    dc = DataCache()
    dc._pitchers_df = _roster_df(guid="g_pos")

    assert dc.get_alpb_id("g_pos") == "555"
    assert len(calls) == 1

    # Even long past the negative TTL window, a positive id is never refetched.
    dc._alpb_ids["g_pos"] = ("555", time.monotonic() - (NEGATIVE_ID_TTL_SECONDS + 100))
    assert dc.get_alpb_id("g_pos") == "555"
    assert len(calls) == 1


def test_negative_alpb_id_expires(monkeypatch):
    calls = []

    def fake_info(fname, lname):
        calls.append((fname, lname))
        return None

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitcher_info", fake_info)

    dc = DataCache()
    dc._pitchers_df = _roster_df(guid="g_neg")

    assert dc.get_alpb_id("g_neg") is None
    assert len(calls) == 1

    # Within the negative TTL → cached, no refetch.
    assert dc.get_alpb_id("g_neg") is None
    assert len(calls) == 1

    # Expire the negative entry → it retries.
    dc._alpb_ids["g_neg"] = (None, time.monotonic() - (NEGATIVE_ID_TTL_SECONDS + 1))
    assert dc.get_alpb_id("g_neg") is None
    assert len(calls) == 2


# ── Concurrency (lock prevents double-fetch) ──────────────────────────────

def test_concurrent_refresh_does_not_double_fetch(monkeypatch):
    calls = []
    started = threading.Event()
    release = threading.Event()

    def slow_fetch():
        calls.append(1)
        started.set()
        release.wait(timeout=5)
        return _roster_df()

    monkeypatch.setattr("python_app.lib.cache.fetch_all_pitchers_combined", slow_fetch)

    dc = DataCache()  # a brand-new cache is stale (never loaded)
    assert dc.roster_is_stale()

    t1 = threading.Thread(target=dc.refresh_roster_if_stale)
    t1.start()
    assert started.wait(timeout=5), "first refresh never started fetching"

    # A second refresh while the first is mid-fetch must be a no-op.
    t2 = threading.Thread(target=dc.refresh_roster_if_stale)
    t2.start()
    t2.join(timeout=5)
    assert not t2.is_alive()
    assert len(calls) == 1  # only one fetch in flight

    release.set()
    t1.join(timeout=5)
    assert len(calls) == 1


# ── Pitch data / season stats TTLs ────────────────────────────────────────

def _pitch_df(speed: float = 92.0) -> pd.DataFrame:
    return pd.DataFrame({"rel_speed": [speed], "auto_pitch_type": ["Fastball"]})


def _stats_df(era: float = 3.50) -> pd.DataFrame:
    return pd.DataFrame({"name": ["ALPB 2026"], "era": [era]})


def test_pitch_data_expires_and_refetches(monkeypatch):
    calls = []

    def fake_pitches(player_id):
        calls.append(player_id)
        return _pitch_df(90.0 + len(calls))

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", fake_pitches)

    dc = DataCache()
    assert dc.get_pitch_data("p1")[0]["rel_speed"] == 91.0
    assert len(calls) == 1

    # Age the entry past its TTL → today's pitches are picked up.
    dc._pitch_data["p1"] = (dc._pitch_data["p1"][0], time.monotonic() - (PITCH_DATA_TTL_SECONDS + 1))
    assert dc.get_pitch_data("p1")[0]["rel_speed"] == 92.0
    assert len(calls) == 2


def test_fresh_pitch_data_not_refetched(monkeypatch):
    calls = []

    def fake_pitches(player_id):
        calls.append(player_id)
        return _pitch_df()

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", fake_pitches)

    dc = DataCache()
    dc.get_pitch_data("p1")
    dc.get_pitch_data("p1")
    assert len(calls) == 1


def test_empty_pitch_data_retried_sooner_than_populated(monkeypatch):
    # The whole point of the negative TTL — an empty result must be cheap to retry.
    assert NEGATIVE_PITCH_DATA_TTL_SECONDS < PITCH_DATA_TTL_SECONDS

    calls = []

    def fake_pitches(player_id):
        calls.append(player_id)
        return pd.DataFrame()

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", fake_pitches)

    dc = DataCache()
    assert dc.get_pitch_data("p1") is None
    assert len(calls) == 1

    # Within the negative TTL → cached, no refetch.
    assert dc.get_pitch_data("p1") is None
    assert len(calls) == 1

    # Past the negative TTL but well inside the populated TTL → exactly one retry.
    dc._pitch_data["p1"] = (None, time.monotonic() - (NEGATIVE_PITCH_DATA_TTL_SECONDS + 1))
    assert dc.get_pitch_data("p1") is None
    assert len(calls) == 2


def test_pitch_refetch_failure_keeps_previous_records(monkeypatch):
    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: _pitch_df())
    dc = DataCache()
    records = dc.get_pitch_data("p1")
    assert records and records[0]["rel_speed"] == 92.0

    # (a) None on refetch → previous records retained.
    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: None)
    dc._pitch_data["p1"] = (records, time.monotonic() - (PITCH_DATA_TTL_SECONDS + 1))
    assert dc.get_pitch_data("p1") == records  # never blanked by a blip

    # (b) Empty frame on refetch → previous records retained.
    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: pd.DataFrame())
    dc._pitch_data["p1"] = (records, time.monotonic() - (PITCH_DATA_TTL_SECONDS + 1))
    assert dc.get_pitch_data("p1") == records


def test_pitch_refetch_failure_backs_off_instead_of_hammering(monkeypatch):
    # A kept-on-failure entry must be restamped, or a sustained ALPB outage turns
    # every view (and every page of a team PDF) into its own upstream request.
    assert REFETCH_BACKOFF_SECONDS < PITCH_DATA_TTL_SECONDS

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: _pitch_df())
    dc = DataCache()
    records = dc.get_pitch_data("p1")

    calls = []

    def down(player_id):
        calls.append(player_id)
        return None

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", down)
    dc._pitch_data["p1"] = (records, time.monotonic() - (PITCH_DATA_TTL_SECONDS + 1))

    for _ in range(50):
        assert dc.get_pitch_data("p1") == records
    assert len(calls) == 1  # one retry, then served from the backed-off entry

    # Past the backoff → exactly one more retry.
    dc._pitch_data["p1"] = (records, time.monotonic() - (PITCH_DATA_TTL_SECONDS + 1))
    dc.get_pitch_data("p1")
    assert len(calls) == 2


def test_season_stats_expires_and_refetches(monkeypatch):
    calls = []

    def fake_stats(guid):
        calls.append(guid)
        return _stats_df(3.00 + len(calls))

    monkeypatch.setattr("python_app.lib.cache.fetch_iscore_player_stats", fake_stats)

    dc = DataCache()
    dc._pitchers_df = _roster_df(guid="g1")

    assert dc.get_season_stats("g1")["era"].iloc[0] == 4.00
    assert len(calls) == 1

    dc._season_stats["g1"] = (dc._season_stats["g1"][0], time.monotonic() - (SEASON_STATS_TTL_SECONDS + 1))
    assert dc.get_season_stats("g1")["era"].iloc[0] == 5.00
    assert len(calls) == 2


def test_fresh_season_stats_not_refetched(monkeypatch):
    calls = []

    def fake_stats(guid):
        calls.append(guid)
        return _stats_df()

    monkeypatch.setattr("python_app.lib.cache.fetch_iscore_player_stats", fake_stats)

    dc = DataCache()
    dc._pitchers_df = _roster_df(guid="g1")

    dc.get_season_stats("g1")
    dc.get_season_stats("g1")
    assert len(calls) == 1


def test_season_stats_refetch_failure_keeps_previous_line(monkeypatch):
    monkeypatch.setattr("python_app.lib.cache.fetch_iscore_player_stats", lambda guid: _stats_df())
    dc = DataCache()
    dc._pitchers_df = _roster_df(guid="g1")
    first = dc.get_season_stats("g1")
    assert first is not None and not first.empty

    def boom(guid):
        raise RuntimeError("iScore unreachable")

    monkeypatch.setattr("python_app.lib.cache.fetch_iscore_player_stats", boom)
    dc._season_stats["g1"] = (first, time.monotonic() - (SEASON_STATS_TTL_SECONDS + 1))
    again = dc.get_season_stats("g1")
    assert again is not None and not again.empty  # never blanked by a blip


def test_season_stats_refetch_failure_backs_off_instead_of_hammering(monkeypatch):
    monkeypatch.setattr("python_app.lib.cache.fetch_iscore_player_stats", lambda guid: _stats_df())
    dc = DataCache()
    dc._pitchers_df = _roster_df(guid="g1")
    first = dc.get_season_stats("g1")

    calls = []

    def down(guid):
        calls.append(guid)
        raise RuntimeError("iScore unreachable")

    monkeypatch.setattr("python_app.lib.cache.fetch_iscore_player_stats", down)
    dc._season_stats["g1"] = (first, time.monotonic() - (SEASON_STATS_TTL_SECONDS + 1))

    for _ in range(50):
        assert dc.get_season_stats("g1") is not None
    assert len(calls) == 1  # one retry, then served from the backed-off entry


def test_empty_season_stats_frame_does_not_raise(monkeypatch):
    # A DataFrame must only ever be tested with `is None` / `.empty` — bare
    # truthiness raises ValueError and would surface as a 500 on the stats card.
    monkeypatch.setattr("python_app.lib.cache.fetch_iscore_player_stats", lambda guid: _stats_df())
    dc = DataCache()
    dc._pitchers_df = _roster_df(guid="g1")
    dc._season_stats["g1"] = (pd.DataFrame(), time.monotonic() - (SEASON_STATS_TTL_SECONDS + 1))

    result = dc.get_season_stats("g1")
    assert result is not None and not result.empty


# ── Pitch-data cache is bounded ───────────────────────────────────────────────
#
# Expiry alone never freed memory: an expired entry was overwritten on the next
# fetch of that same pitcher, or kept forever if he was never viewed again, and
# nothing capped how many pitchers accumulated. Pitch rows are the only thing in
# this cache big enough to matter — ~4.4 KB per pitch on the wire, and a starter
# carries well over a thousand — against a 1024 MB task.

def test_pitch_cache_evicts_the_least_recently_used(monkeypatch):
    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: _pitch_df())
    monkeypatch.setattr("python_app.lib.cache.PITCH_DATA_MAX_PITCHERS", 3)

    dc = DataCache()
    for pid in ("p1", "p2", "p3"):
        dc.get_pitch_data(pid)
    dc.get_pitch_data("p1")          # p1 is now the most recently used
    dc.get_pitch_data("p4")          # over the cap → p2 is the oldest use

    assert set(dc._pitch_data) == {"p1", "p3", "p4"}


def test_pitch_cache_holds_a_whole_roster(monkeypatch):
    """A team report walks one roster in a single pass — 34 for High Point.

    A cap below that would have the export evicting its own earlier pages while
    it ran, re-fetching pitchers it had already paid for.
    """
    from python_app.config import PITCH_DATA_MAX_PITCHERS as configured

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: _pitch_df())
    dc = DataCache()
    for i in range(34):
        dc.get_pitch_data(f"p{i}")

    assert configured >= 34, "the cap must clear the largest roster in the league"
    assert len(dc._pitch_data) == 34, "a single team export evicted its own pages"


def test_a_kept_entry_after_a_failed_refetch_still_counts_against_the_cap(monkeypatch):
    """The keep-what-we-have path must not slip past eviction."""
    monkeypatch.setattr("python_app.lib.cache.PITCH_DATA_MAX_PITCHERS", 2)
    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: _pitch_df())

    dc = DataCache()
    dc.get_pitch_data("p1")
    dc._pitch_data["p1"] = (dc._pitch_data["p1"][0], time.monotonic() - (PITCH_DATA_TTL_SECONDS + 1))

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: None)
    assert dc.get_pitch_data("p1") is not None      # kept, as designed

    monkeypatch.setattr("python_app.lib.cache.fetch_alpb_pitches", lambda pid: _pitch_df())
    dc.get_pitch_data("p2")
    dc.get_pitch_data("p3")

    assert len(dc._pitch_data) == 2
