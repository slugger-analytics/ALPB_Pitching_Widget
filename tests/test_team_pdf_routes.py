"""Tests for the HTTP routes backing the one-click team report.

A 34-man team report is 34 page renders. Done inside a single Dash callback it
runs past gunicorn's 180s worker timeout and the ALB answers 504 — High Point
failed twice under live measurement and Charleston (16 pitchers, warm cache)
needed 173.5s. The report is therefore assembled in the browser: these routes
hand out the roster and one single-page PDF at a time, and ``assets/team_pdf.js``
merges them with pdf-lib. Same pattern as slugger-outfielder ``aaf3330``.

What must hold:
  * a request serves exactly ONE page, so no request can be long;
  * the roster the browser merges is the same list, in the same order, that the
    old server-side loop paged through (``_team_sorted``);
  * the routes live under the Dash base path — prod runs
    ``DASH_URL_BASE_PATHNAME=/widgets/pitching/`` and anything registered at the
    root is unreachable through the ALB (``/healthz`` already is);
  * page rendering stays serialised, because pyplot and kaleido are both
    process-global and a team export now means concurrent requests.
"""

from __future__ import annotations

import io
import threading
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from flask import Flask

from python_app.features import pdf_export, team_pdf

_ALL_TEAMS = "__ALL_TEAMS__"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def roster() -> pd.DataFrame:
    """A roster with the two shapes ``_team_sorted`` exists to collapse.

    ``g2`` appears twice (same guid, duplicated feed row) and "Zeb Zenith"
    appears twice with no guid at all.
    """
    return pd.DataFrame([
        {"iscore_guid": "g2", "fname": "Blake", "lname": "Bolt",
         "full_name": "Blake Bolt", "teamname": "Test Team"},
        {"iscore_guid": "g1", "fname": "Alex", "lname": "Ace",
         "full_name": "Alex Ace", "teamname": "Test Team"},
        {"iscore_guid": "g2", "fname": "Blake", "lname": "Bolt",
         "full_name": "Blake Bolt", "teamname": "Test Team"},
        {"iscore_guid": "", "fname": "Zeb", "lname": "Zenith",
         "full_name": "Zeb Zenith", "teamname": "Test Team"},
        {"iscore_guid": "", "fname": "Zeb", "lname": "Zenith",
         "full_name": "Zeb Zenith", "teamname": "Test Team"},
    ])


class _StubCache:
    """Stands in for the module-level roster/pitch cache."""

    def __init__(self, players: pd.DataFrame) -> None:
        self._players = players

    def get_players(self, team_name: str | None = None) -> pd.DataFrame:
        if not team_name:
            return self._players
        return self._players[self._players["teamname"] == team_name]

    def get_player_by_guid(self, guid: str | None) -> pd.Series | None:
        if not guid:
            return None
        rows = self._players[self._players["iscore_guid"].astype(str) == str(guid)]
        return rows.iloc[0] if not rows.empty else None

    def get_season_stats(self, guid: str) -> None:
        return None

    def get_alpb_id(self, guid: str) -> None:
        return None

    def get_pitch_data(self, alpb_id: str) -> list:
        return []


def _stub_page(record: list[dict[str, Any]]):
    """Replacement for ``_append_player_page``: records kwargs, draws a page.

    A real page is still written so ``PdfPages`` closes over valid output and the
    page-count assertions stay meaningful.
    """
    def _append(**kwargs: Any) -> None:
        record.append(kwargs)
        fig = plt.figure(figsize=(8.5, 11))
        kwargs["pdf"].savefig(fig)
        plt.close(fig)

    return _append


@pytest.fixture
def client(roster, monkeypatch):
    """A Flask test client with the routes mounted at the root."""
    stub = _StubCache(roster)
    monkeypatch.setattr(team_pdf, "cache", stub)
    monkeypatch.setattr(pdf_export, "cache", stub)

    server = Flask(__name__)
    team_pdf.register_routes(server, "/")
    return server.test_client()


def _pages(pdf_bytes: bytes) -> int:
    from pypdf import PdfReader

    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


# ── 1. Roster: the browser must merge exactly what the server used to page ────

def test_team_roster_matches_team_sorted(client, roster) -> None:
    resp = client.get("/api/team-roster?team=Test+Team")

    assert resp.status_code == 200
    body = resp.get_json()
    expected = [
        {"id": "g1", "name": "Alex Ace"},
        {"id": "g2", "name": "Blake Bolt"},
    ]
    assert body["players"] == expected
    assert body["team"] == "Test Team"


def test_team_roster_reports_records_it_cannot_serve(client) -> None:
    """Guid-less records can't be fetched by guid, so say so rather than drop them silently."""
    body = client.get("/api/team-roster?team=Test+Team").get_json()

    assert body["excluded"] == 1  # the two Zeb Zenith rows collapse to one


def test_team_roster_rejects_all_teams(client) -> None:
    assert client.get(f"/api/team-roster?team={_ALL_TEAMS}").status_code == 400
    assert client.get("/api/team-roster").status_code == 400


def test_team_roster_unknown_team_is_empty_not_an_error(client) -> None:
    resp = client.get("/api/team-roster?team=Nowhere+Nine")

    assert resp.status_code == 200
    assert resp.get_json()["players"] == []


# ── 2. One request = one page, which is the whole point ───────────────────────

def test_player_pdf_serves_exactly_one_page(client, monkeypatch) -> None:
    monkeypatch.setattr(pdf_export, "_append_player_page", _stub_page([]))

    resp = client.get("/api/player-pdf?guid=g1")

    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF-")
    assert _pages(resp.data) == 1
    assert "Alex Ace Pitcher Report.pdf" in resp.headers["Content-Disposition"]


def test_player_pdf_unknown_guid_is_404(client) -> None:
    assert client.get("/api/player-pdf?guid=nope").status_code == 404
    assert client.get("/api/player-pdf").status_code == 404


# ── 3. The export must not silently disagree with the screen ──────────────────

def test_player_pdf_follows_the_batter_side(client, monkeypatch) -> None:
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(pdf_export, "_append_player_page", _stub_page(seen))

    resp = client.get("/api/player-pdf?guid=g1&side=Left")

    assert seen[0]["batter_side"] == "Left"
    assert "vs LHB" in resp.headers["Content-Disposition"]


def test_player_pdf_follows_the_pitch_tag(client, monkeypatch) -> None:
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(pdf_export, "_append_player_page", _stub_page(seen))

    client.get("/api/player-pdf?guid=g1&tag=tagged_pitch_type")

    assert seen[0]["pitch_tag"] == "tagged_pitch_type"


def test_player_pdf_falls_back_on_an_unknown_tag_or_side(client, monkeypatch) -> None:
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(pdf_export, "_append_player_page", _stub_page(seen))

    client.get("/api/player-pdf?guid=g1&tag=../../etc&side=Sideways")

    assert seen[0]["pitch_tag"] == "auto_pitch_type"
    assert seen[0]["batter_side"] == "All"


# ── 4. Mounted under the Dash base path, or the ALB never reaches it ──────────

def test_routes_live_under_the_dash_base_path(roster, monkeypatch) -> None:
    """`/healthz` is registered at the root and is unreachable in prod — don't repeat it."""
    stub = _StubCache(roster)
    monkeypatch.setattr(team_pdf, "cache", stub)
    monkeypatch.setattr(pdf_export, "cache", stub)

    server = Flask(__name__)
    team_pdf.register_routes(server, "/widgets/pitching/")
    rules = {str(r) for r in server.url_map.iter_rules()}

    assert "/widgets/pitching/api/team-roster" in rules
    assert "/widgets/pitching/api/player-pdf" in rules
    assert "/api/team-roster" not in rules


def test_base_path_without_a_trailing_slash_still_mounts(roster, monkeypatch) -> None:
    stub = _StubCache(roster)
    monkeypatch.setattr(team_pdf, "cache", stub)
    monkeypatch.setattr(pdf_export, "cache", stub)

    server = Flask(__name__)
    team_pdf.register_routes(server, "/widgets/pitching")
    rules = {str(r) for r in server.url_map.iter_rules()}

    assert "/widgets/pitching/api/player-pdf" in rules


# ── 5. pyplot and kaleido are process-global; renders must not overlap ────────

def test_page_rendering_is_serialised(roster, monkeypatch) -> None:
    """Two concurrent renders must never be inside the page builder together.

    matplotlib's pyplot state and kaleido's scope are process-global. A team
    export is now N requests against a worker with 2 threads, so overlap is no
    longer hypothetical — this is the outfielder's `pyplot-global-state-race`
    waiting to happen here.
    """
    monkeypatch.setattr(pdf_export, "cache", _StubCache(roster))
    live = 0
    peak = 0
    guard = threading.Lock()

    def _slow_page(**kwargs: Any) -> None:
        nonlocal live, peak
        with guard:
            live += 1
            peak = max(peak, live)
        time.sleep(0.05)
        fig = plt.figure(figsize=(8.5, 11))
        kwargs["pdf"].savefig(fig)
        plt.close(fig)
        with guard:
            live -= 1

    monkeypatch.setattr(pdf_export, "_append_player_page", _slow_page)
    player = roster.iloc[1]

    def _render() -> None:
        pdf_export.render_player_pdf_bytes(
            name="Alex Ace", player=player, season_stats=None,
            pitch_data=None, pitch_tag="auto_pitch_type", batter_side=None,
        )

    threads = [threading.Thread(target=_render) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak == 1, f"{peak} concurrent page renders — pyplot state is shared"


# ── 6. The 504 path must not come back ────────────────────────────────────────

def test_the_download_callback_no_longer_renders_a_whole_team() -> None:
    """The team button must not be wired to a server-side callback again."""
    from dash._callback import GLOBAL_CALLBACK_MAP

    spec = GLOBAL_CALLBACK_MAP["download-pdf.data"]
    ids = [dep["id"] for dep in spec["inputs"] + spec["state"]]

    assert "download-team-pdf-btn" not in ids
    assert not hasattr(pdf_export, "_generate_team_pdf")


def test_the_button_is_wired_to_the_browser_merge() -> None:
    """Layout + clientside wiring: the pieces the browser needs must all be present."""
    from dash.development.base_component import Component

    from python_app import app as app_module

    def _ids(node: object) -> list[str]:
        found: list[str] = []
        if isinstance(node, Component):
            if getattr(node, "id", None):
                found.append(node.id)
            found += _ids(getattr(node, "children", None))
        elif isinstance(node, (list, tuple)):
            for child in node:
                found += _ids(child)
        return found

    ids = _ids(app_module.app.layout)
    assert "download-team-pdf-btn" in ids
    assert "team-pdf-status" in ids

    scripts = " ".join(app_module.app.config.external_scripts)
    assert "pdf-lib" in scripts, "the browser cannot merge pages without pdf-lib"

    # This is the spec Dash serialises to the browser, so it is what actually runs.
    spec = next(
        cb for cb in app_module.app._callback_list
        if cb["output"] == "team-pdf-status.children"
    )
    fn = spec["clientside_function"]
    assert (getattr(fn, "namespace", None) or fn["namespace"]) == "teamPdf"
    assert [dep["id"] for dep in spec["inputs"]] == ["download-team-pdf-btn"]
    assert [dep["id"] for dep in spec["state"]] == [
        "selected-team", "tag-choice", "batter-side",
    ]


def test_routes_are_mounted_on_the_real_server() -> None:
    """Registered against the live Dash server, under the configured base path."""
    from python_app import app as app_module

    rules = {str(r) for r in app_module.server.url_map.iter_rules()}
    base = app_module._URL_BASE_PATHNAME

    assert f"{base}api/player-pdf" in rules
    assert f"{base}api/team-roster" in rules


def test_headshots_are_fetched_once_per_url(monkeypatch) -> None:
    """A team export is N pages; the same headshot host shouldn't be hit N times."""
    calls: list[str] = []

    class _Resp:
        content = b""

        def raise_for_status(self) -> None:
            return None

    def _get(url: str, timeout: int = 10):
        calls.append(url)
        return _Resp()

    pdf_export._download_photo.cache_clear()
    monkeypatch.setattr(pdf_export.requests, "get", _get)
    monkeypatch.setattr(pdf_export.Image, "open", lambda buf: "image")

    pdf_export._download_photo("http://example.test/a.jpg")
    pdf_export._download_photo("http://example.test/a.jpg")

    assert calls == ["http://example.test/a.jpg"]
