"""Tests for the batter-side filter in the PDF export.

The exported report must never silently disagree with the screen: pitch movement
and pitch usage follow the on-screen ``batter-side`` radio, the heatmaps stay
split by side (they ARE the side split), and every page states which batters it
covers in the banner, the filtered section labels, and the filename.
"""

from __future__ import annotations

import os
import tempfile

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.backends.backend_pdf import PdfPages

from python_app.features import pdf_export, scatter_plots
from python_app.features.pdf_export import (
    _append_player_page,
    _build_page,
    _chart_empty_text,
    _draw_banner,
    _filename_side_suffix,
    _generate_pdf,
    _generate_team_pdf,
)


@pytest.fixture
def pitches() -> pd.DataFrame:
    """Two Right-handed batters and one Left-handed batter."""
    return pd.DataFrame([
        {"batter_side": "Right", "auto_pitch_type": "Fastball", "rel_speed": 92.0,
         "horz_break": 5.0, "induced_vert_break": 15.0, "balls": 0, "strikes": 0,
         "plate_loc_side": 0.2, "plate_loc_height": 2.5},
        {"batter_side": "Right", "auto_pitch_type": "Slider", "rel_speed": 84.0,
         "horz_break": -3.0, "induced_vert_break": 2.0, "balls": 1, "strikes": 0,
         "plate_loc_side": -0.4, "plate_loc_height": 2.1},
        {"batter_side": "Left", "auto_pitch_type": "Fastball", "rel_speed": 91.0,
         "horz_break": 6.0, "induced_vert_break": 14.0, "balls": 0, "strikes": 1,
         "plate_loc_side": 0.1, "plate_loc_height": 3.0},
    ])


@pytest.fixture
def player() -> pd.Series:
    return pd.Series({
        "iscore_guid": "g1",
        "fname": "Alex",
        "lname": "Ace",
        "full_name": "Alex Ace",
        "teamname": "Test Team",
        "throws": "R",
    })


def _capture_page(monkeypatch) -> dict:
    """Replace ``_build_page`` with a stub that records its keyword arguments."""
    captured: dict = {}

    def fake_build_page(pdf, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(pdf_export, "_build_page", fake_build_page)
    monkeypatch.setattr(pdf_export, "_plotly_to_image", lambda *a, **k: None)
    return captured


# ── Heatmaps stay split by side (never double-filtered) ───────────────────────

def test_heatmaps_still_render_both_sides(monkeypatch, pitches, player) -> None:
    captured = _capture_page(monkeypatch)

    _append_player_page(
        pdf=None,
        name="Alex Ace",
        player=player,
        season_stats=None,
        pitch_data=pitches,
        pitch_tag="auto_pitch_type",
        batter_side="Left",
    )

    assert len(captured["heatmap_images"]) == 2


def test_heatmaps_survive_an_empty_selected_side(monkeypatch, pitches, player) -> None:
    right_only = pitches[pitches["batter_side"] == "Right"]
    captured = _capture_page(monkeypatch)

    _append_player_page(
        pdf=None,
        name="Alex Ace",
        player=player,
        season_stats=None,
        pitch_data=right_only,
        pitch_tag="auto_pitch_type",
        batter_side="Left",
    )

    # Both heatmaps still build off the unfiltered frame ...
    assert len(captured["heatmap_images"]) == 2
    # ... while the movement charts are skipped rather than rasterised blank.
    assert captured["scatter_images"] == []


# ── Movement + usage follow the batter-side radio ─────────────────────────────

def _capture_frames(monkeypatch) -> dict:
    """Record the frames handed to the scatter builder and the usage pivot."""
    frames: dict = {"scatter": [], "split": []}
    real_split = pdf_export.compute_pitch_split

    class _StubFig:
        def update_layout(self, *a, **k):
            return self

    def fake_scatter(df, x_axis, y_axis, tag):
        frames["scatter"].append(df)
        return _StubFig()

    def fake_split(df, tag):
        frames["split"].append(df)
        return real_split(df, tag)

    monkeypatch.setattr(pdf_export, "build_scatter", fake_scatter)
    monkeypatch.setattr(pdf_export, "compute_pitch_split", fake_split)
    return frames


def test_movement_and_usage_use_only_the_selected_side(monkeypatch, pitches, player) -> None:
    _capture_page(monkeypatch)
    frames = _capture_frames(monkeypatch)

    _append_player_page(
        pdf=None,
        name="Alex Ace",
        player=player,
        season_stats=None,
        pitch_data=pitches,
        pitch_tag="auto_pitch_type",
        batter_side="Left",
    )

    assert frames["scatter"] and all(len(df) == 1 for df in frames["scatter"])
    assert all(set(df["batter_side"]) == {"Left"} for df in frames["scatter"])
    assert len(frames["split"][0]) == 1


def test_right_side_keeps_both_right_handed_rows(monkeypatch, pitches, player) -> None:
    captured = _capture_page(monkeypatch)
    frames = _capture_frames(monkeypatch)

    _append_player_page(
        pdf=None,
        name="Alex Ace",
        player=player,
        season_stats=None,
        pitch_data=pitches,
        pitch_tag="auto_pitch_type",
        batter_side="Right",
    )

    assert all(len(df) == 2 for df in frames["scatter"])
    assert not captured["split_df"].empty


def test_all_batters_is_the_unfiltered_frame(monkeypatch, pitches, player) -> None:
    _capture_page(monkeypatch)
    frames = _capture_frames(monkeypatch)

    _append_player_page(
        pdf=None,
        name="Alex Ace",
        player=player,
        season_stats=None,
        pitch_data=pitches,
        pitch_tag="auto_pitch_type",
        batter_side="All",
    )

    assert all(len(df) == 3 for df in frames["scatter"])
    assert len(frames["split"][0]) == 3


# ── An empty side must still produce a real page ──────────────────────────────

def test_empty_side_still_writes_a_pdf(monkeypatch, pitches, player) -> None:
    right_only = pitches[pitches["batter_side"] == "Right"]
    # Stub only the plotly→raster step (kaleido shells out to a browser); the
    # real matplotlib/PdfPages page assembly still runs.
    monkeypatch.setattr(pdf_export, "_plotly_to_image", lambda *a, **k: None)

    path = _generate_pdf("Alex Ace", player, None, right_only, "auto_pitch_type", "Left")
    try:
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


# ── Empty-state copy ──────────────────────────────────────────────────────────

def test_chart_empty_text_wording() -> None:
    assert _chart_empty_text(True, False, "Left") == "No pitches vs LHB"
    assert _chart_empty_text(True, False, "Right") == "No pitches vs RHB"
    # A chart that WAS built but could not be rasterised is a kaleido problem,
    # never a batter-side one.
    assert _chart_empty_text(True, True, "Left") == "Install kaleido to\nenable chart export"
    assert _chart_empty_text(False, False, "All") == "No pitch data"


def test_chart_empty_text_matches_the_web_placeholder() -> None:
    fig = scatter_plots._empty_side_figure("Left")
    web_text = " ".join(a.text for a in fig.layout.annotations if a.text)
    assert _chart_empty_text(True, False, "Left") == web_text


# ── Stamps: banner, section labels, filename ──────────────────────────────────

def _section_labels(monkeypatch, batter_side: str | None, player: pd.Series) -> list[str]:
    labels: list[str] = []
    monkeypatch.setattr(
        pdf_export, "_section_label", lambda fig, y, text: labels.append(text)
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    try:
        with PdfPages(tmp.name) as pdf:
            _build_page(
                pdf,
                name="Alex Ace",
                player=player,
                season_stats=None,
                split_df=None,
                scatter_images=[],
                heatmap_images=[],
                has_pitches=False,
                batter_side=batter_side,
            )
    finally:
        os.unlink(tmp.name)
    return labels


def test_section_labels_stamp_only_the_filtered_sections(monkeypatch, player) -> None:
    labels = _section_labels(monkeypatch, "Left", player)

    assert "PITCH MOVEMENT  —  VS LHB" in labels
    assert "PITCH USAGE BY COUNT  —  VS LHB" in labels
    # The heatmaps are the side split itself — no suffix is the signal.
    assert "PITCH HEATMAPS" in labels


def test_section_labels_unchanged_for_all_batters(monkeypatch, player) -> None:
    labels = _section_labels(monkeypatch, "All", player)

    assert "PITCH MOVEMENT" in labels
    assert "PITCH USAGE BY COUNT" in labels
    assert "PITCH HEATMAPS" in labels


def _banner_texts(batter_side: str | None) -> str:
    fig = plt.figure(figsize=(8.5, 11))
    try:
        _draw_banner(fig, "Alex Ace", batter_side)
        return " ".join(t.get_text() for ax in fig.axes for t in ax.texts)
    finally:
        plt.close(fig)


def test_banner_always_states_the_batter_side() -> None:
    assert "vs LHB" in _banner_texts("Left")
    assert "vs RHB" in _banner_texts("Right")
    assert "All Batters" in _banner_texts("All")
    assert "All Batters" in _banner_texts(None)


def test_filename_side_suffix() -> None:
    assert _filename_side_suffix("Left") == " vs LHB"
    assert _filename_side_suffix("Right") == " vs RHB"
    assert _filename_side_suffix("All") == ""
    assert _filename_side_suffix(None) == ""


# ── Team PDF: every page inherits the same side ───────────────────────────────

def test_team_pdf_passes_the_side_to_every_page(monkeypatch) -> None:
    team = pd.DataFrame([
        {"iscore_guid": "g1", "fname": "Alex", "lname": "Ace",
         "full_name": "Alex Ace", "teamname": "Test Team"},
        {"iscore_guid": "g2", "fname": "Blake", "lname": "Bolt",
         "full_name": "Blake Bolt", "teamname": "Test Team"},
    ])
    sides: list[str | None] = []

    monkeypatch.setattr(pdf_export.cache, "get_season_stats", lambda guid: None)
    monkeypatch.setattr(pdf_export, "_pitch_df_for_player", lambda p: None)
    monkeypatch.setattr(
        pdf_export,
        "_append_player_page",
        lambda **kwargs: sides.append(kwargs["batter_side"]),
    )

    path = _generate_team_pdf(team, "auto_pitch_type", "Left")
    try:
        assert sides == ["Left", "Left"]
    finally:
        os.unlink(path)
