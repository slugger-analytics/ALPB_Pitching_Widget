"""A page that fails must not be mistaken for the end of a pitcher's season.

``_fetch_alpb_page`` used to return ``[]`` both when a page was genuinely empty
and when it timed out or answered non-200, and the paging loop breaks on ``[]``.
A failure on page 2 of 4 therefore produced a NON-EMPTY DataFrame holding only
page 1, which ``DataCache.get_pitch_data`` cached as that pitcher's complete
season — its "never serve empty over good data" guard only tests
``df is None or df.empty``, and a 75%-truncated frame is neither.

Since PITCH_DATA_TTL_SECONDS makes entries expire and refetch, that meant a
correctly cached season could be silently OVERWRITTEN by a truncated one and
stamped fresh for another full TTL, then printed into the team PDF handed to
staff who never saw the screen.
"""

from __future__ import annotations

import time

import pytest

import python_app.lib.api as api
from python_app.lib.cache import DataCache


class _Resp:
    def __init__(self, rows, status=200):
        self._rows = rows
        self.status_code = status

    def json(self):
        return {"data": self._rows}


def _rows(page, n=500):
    return [{"pitch": f"p{page}-{i}"} for i in range(n)]


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """Keep the bounded retry's backoff out of the test's wall clock."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def _install_pages(monkeypatch, failing_page=None, error=None, status=200):
    """Serve 4 pages of 500 rows; optionally break one of them."""
    calls = {"n": 0}

    def _get(url, params=None, timeout=None, **kwargs):
        page = (params or {}).get("page")
        calls["n"] += 1
        if page == failing_page:
            if error is not None:
                raise error
            return _Resp([], status=status)
        if page and page <= 4:
            return _Resp(_rows(page))
        return _Resp([])

    monkeypatch.setattr(api._alpb_session, "get", _get)
    return calls


def test_a_healthy_fetch_returns_every_page(monkeypatch):
    _install_pages(monkeypatch)
    df = api.fetch_alpb_pitches("pitcher-1")
    assert df is not None and len(df) == 2000


def test_a_timed_out_page_is_not_end_of_data(monkeypatch):
    import requests

    _install_pages(monkeypatch, failing_page=2,
                   error=requests.exceptions.ReadTimeout("boom"))
    df = api.fetch_alpb_pitches("pitcher-1")
    # Previously: a 500-row frame — 25% of the season, indistinguishable from a
    # complete one to every caller downstream.
    assert df is None


def test_a_non_200_page_is_not_end_of_data(monkeypatch):
    _install_pages(monkeypatch, failing_page=2, status=429)
    assert api.fetch_alpb_pitches("pitcher-1") is None


def test_a_transient_blip_is_retried_rather_than_discarding_a_good_season(monkeypatch):
    import requests

    state = {"failures": 0}

    def _get(url, params=None, timeout=None, **kwargs):
        page = (params or {}).get("page")
        if page == 2 and state["failures"] < 1:
            state["failures"] += 1
            raise requests.exceptions.ReadTimeout("one blip")
        if page and page <= 4:
            return _Resp(_rows(page))
        return _Resp([])

    monkeypatch.setattr(api._alpb_session, "get", _get)
    df = api.fetch_alpb_pitches("pitcher-1")
    assert df is not None and len(df) == 2000, "a single blip should not cost the season"


def test_a_truncated_refetch_never_overwrites_a_good_cached_season(monkeypatch):
    """The end-to-end shape of the defect, driven through the real cache."""
    import requests

    cache = DataCache()

    _install_pages(monkeypatch)
    first = cache.get_pitch_data("pitcher-1")
    assert first is not None and len(first) == 2000

    # Expire the entry, then refetch while page 2 is down for good.
    records, _ = cache._pitch_data["pitcher-1"]
    cache._pitch_data["pitcher-1"] = (records, time.monotonic() - 10_000)
    _install_pages(monkeypatch, failing_page=2,
                   error=requests.exceptions.ReadTimeout("still down"))

    second = cache.get_pitch_data("pitcher-1")
    assert second is not None and len(second) == 2000, \
        "the complete season was replaced by a truncated one"
