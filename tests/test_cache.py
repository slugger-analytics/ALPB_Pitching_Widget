"""Tests for periodic roster + cache refresh (P1).

A Fargate container lives for days, so the roster and negative ALPB-id lookups
must expire and refresh in place — otherwise newly signed pitchers never appear
without a container restart. A transient API failure must never wipe the
already-served roster.
"""

from __future__ import annotations

import threading
import time

import pandas as pd

from python_app.config import NEGATIVE_ID_TTL_SECONDS, ROSTER_TTL_SECONDS
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
