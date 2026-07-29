"""Callback-level tests for the batter-side filter.

The two movement scatter callbacks and the pitch-usage table callback each gain a
trailing ``batter-side`` input. Heatmaps stay split by side but the shared filter
now hardens ``_filter_by_side`` against a missing ``batter_side`` column. The PDF
export deliberately keeps rendering All (no batter-side input) — guarded here.
"""

from __future__ import annotations

import inspect

import pytest
from dash import dash_table, html

from python_app.features import heatmaps, pdf_export, pitch_split, scatter_plots


@pytest.fixture
def records() -> list[dict]:
    """Two Right-handed batters and one Left-handed batter."""
    return [
        {"batter_side": "Right", "auto_pitch_type": "Fastball", "rel_speed": 92.0,
         "horz_break": 5.0, "induced_vert_break": 15.0, "balls": 0, "strikes": 0},
        {"batter_side": "Right", "auto_pitch_type": "Slider", "rel_speed": 84.0,
         "horz_break": -3.0, "induced_vert_break": 2.0, "balls": 1, "strikes": 0},
        {"batter_side": "Left", "auto_pitch_type": "Fastball", "rel_speed": 91.0,
         "horz_break": 6.0, "induced_vert_break": 14.0, "balls": 0, "strikes": 1},
    ]


def _total_points(fig) -> int:
    return sum(len(trace.x) for trace in fig.data if getattr(trace, "x", None) is not None)


def _annotation_texts(fig) -> str:
    return " ".join(a.text for a in fig.layout.annotations if a.text)


# ── Velocity scatter ──────────────────────────────────────────────────────────

def test_vel_plot_all_has_points(records: list[dict]) -> None:
    fig = scatter_plots.update_vel_plot(records, "induced_vert_break", "auto_pitch_type", "All")
    assert len(fig.data) >= 1
    assert _total_points(fig) == 3


def test_vel_plot_left_one_point(records: list[dict]) -> None:
    fig = scatter_plots.update_vel_plot(records, "induced_vert_break", "auto_pitch_type", "Left")
    assert _total_points(fig) == 1


def test_vel_plot_empty_side_shows_annotation(records: list[dict]) -> None:
    right_only = [r for r in records if r["batter_side"] == "Right"]
    fig = scatter_plots.update_vel_plot(right_only, "induced_vert_break", "auto_pitch_type", "Left")
    assert len(fig.data) == 0
    assert "vs LHB" in _annotation_texts(fig)


# ── Break scatter (mirrors the velocity plot) ─────────────────────────────────

def test_break_plot_all_has_points(records: list[dict]) -> None:
    fig = scatter_plots.update_break_plot(records, "auto_pitch_type", "All")
    assert len(fig.data) >= 1
    assert _total_points(fig) == 3


def test_break_plot_left_one_point(records: list[dict]) -> None:
    fig = scatter_plots.update_break_plot(records, "auto_pitch_type", "Left")
    assert _total_points(fig) == 1


def test_break_plot_empty_side_shows_annotation(records: list[dict]) -> None:
    right_only = [r for r in records if r["batter_side"] == "Right"]
    fig = scatter_plots.update_break_plot(right_only, "auto_pitch_type", "Left")
    assert len(fig.data) == 0
    assert "vs LHB" in _annotation_texts(fig)


# ── Pitch-usage table ─────────────────────────────────────────────────────────

def test_pitch_table_all_returns_datatable(records: list[dict]) -> None:
    result = pitch_split.update_pitch_table(records, "auto_pitch_type", "All")
    assert isinstance(result, dash_table.DataTable)


def test_pitch_table_empty_side_returns_message(records: list[dict]) -> None:
    right_only = [r for r in records if r["batter_side"] == "Right"]
    result = pitch_split.update_pitch_table(right_only, "auto_pitch_type", "Left")
    assert isinstance(result, html.P)
    assert "vs LHB" in result.children


# ── Heatmap regression (still split by side, now missing-column safe) ─────────

def test_heatmap_filter_returns_only_right_rows(records: list[dict]) -> None:
    df = heatmaps._filter_by_side(records, "auto_pitch_type", "All", "Right")
    assert len(df) == 2
    assert set(df["batter_side"]) == {"Right"}


def test_heatmap_filter_missing_column_no_keyerror(records: list[dict]) -> None:
    no_side = [{k: v for k, v in r.items() if k != "batter_side"} for r in records]
    df = heatmaps._filter_by_side(no_side, "auto_pitch_type", "All", "Right")
    assert len(df) == 0


# ── PDF convention guard ──────────────────────────────────────────────────────

def test_pdf_export_has_no_batter_side_input() -> None:
    assert "batter-side" not in inspect.getsource(pdf_export)
