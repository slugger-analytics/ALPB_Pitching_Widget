"""
PDF scouting report — single-page portrait letter (8.5 × 11 in).

Callback : triggered by the "Download PDF" button.
Pipeline : pre-render Plotly figures → convert to raster images via kaleido
           → compose everything onto ONE matplotlib page → save as PDF.

Every chart and table reuses the **same public functions** that drive the
Dash UI — nothing is re-implemented here:

    scatter_plots.build_scatter()      → pitch-movement scatter charts
    pitch_split.compute_pitch_split()  → count-based pitch-usage table
"""

from __future__ import annotations

import io
import tempfile
import traceback
from datetime import date
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")                          # headless backend — no GUI

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image

from dash import Input, Output, State, callback, dcc, no_update

from python_app.config import TABLE_HEADER_COLOR
from python_app.features.pitch_split import compute_pitch_split
from python_app.features.scatter_plots import build_scatter
from python_app.lib.cache import cache

if TYPE_CHECKING:
    import plotly.graph_objects as go

# ── Colour palette ────────────────────────────────────────────────────────────
_NAVY:  str = TABLE_HEADER_COLOR          # "#002D72"
_RED:   str = "#C8102E"
_LGRAY: str = "#f5f6fa"
_MGRAY: str = "#dcdde1"

# Scatter-plot column pairs shown in the PDF (x, y)
_SCATTER_PAIRS: list[tuple[str, str]] = [
    ("horz_break", "induced_vert_break"),
    ("rel_speed",  "induced_vert_break"),
    ("rel_speed",  "horz_break"),
]

# ── Kaleido availability (checked once at import time) ────────────────────────
_KALEIDO_OK: bool = False
try:
    import kaleido  # noqa: F401
    _KALEIDO_OK = True
except ImportError:
    print(
        "\n⚠  kaleido is not installed — PDF charts will show placeholder text.\n"
        "   Fix:  pip install 'kaleido>=0.2.1,<1.0'\n"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Dash callback
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("download-pdf", "data"),
    Input("download-pdf-btn", "n_clicks"),
    State("selected-player", "value"),
    State("pitch-data-store", "data"),
    State("tag-choice", "value"),
    prevent_initial_call=True,
)
def download_pdf(
    n_clicks: int | None,
    selected_name: str | None,
    pitch_records: list[dict] | None,
    tag: str | None,
):
    """Generate and send a single-page scouting-report PDF."""
    if not n_clicks or not selected_name:
        return no_update

    player = cache.get_player(selected_name)
    if player is None:
        return no_update

    stats = cache.get_season_stats(player["playerlinkid"])
    pitch_df = pd.DataFrame(pitch_records) if pitch_records else None
    tag = tag or "auto_pitch_type"

    pdf_path = _generate_pdf(selected_name, player, stats, pitch_df, tag)
    return dcc.send_file(pdf_path, filename=f"{selected_name} Pitcher Report.pdf")


# ═══════════════════════════════════════════════════════════════════════════════
#  Image / download helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _plotly_to_image(
    fig: go.Figure,
    width: int = 450,
    height: int = 320,
    scale: int = 2,
) -> np.ndarray | None:
    """Convert a Plotly figure to a NumPy RGBA array for matplotlib.

    Returns *None* when kaleido is missing or conversion fails.
    """
    if not _KALEIDO_OK:
        return None
    try:
        raw = fig.to_image(format="png", width=width, height=height, scale=scale)
        return plt.imread(io.BytesIO(raw))
    except Exception:
        traceback.print_exc()
        return None


def _download_photo(url: str) -> Image.Image | None:
    """Fetch a player headshot from *url*.  Returns a PIL Image or *None*."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  Matplotlib drawing primitives
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_banner(fig: plt.Figure, name: str) -> None:
    """Dark-navy banner across the top of the page."""
    ax = fig.add_axes([0, 0.945, 1, 0.055])
    ax.set_facecolor(_NAVY)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(
        0.5, 0.60, f"{name}  —  Pitching Report",
        ha="center", va="center",
        fontsize=15, fontweight="bold", color="white",
        fontfamily="sans-serif",
    )
    ax.text(
        0.5, 0.15, date.today().strftime("%B %d, %Y"),
        ha="center", va="center",
        fontsize=7, color="#8eafd4", fontfamily="sans-serif",
    )
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])

    # Thin red accent line beneath the banner
    fig.add_artist(plt.Line2D(
        [0, 1], [0.945, 0.945],
        color=_RED, linewidth=2, transform=fig.transFigure, zorder=5,
    ))


def _section_label(fig: plt.Figure, y: float, text: str) -> None:
    """Small caps-style section heading at figure-*y* coordinate."""
    fig.text(
        0.06, y, text,
        fontsize=7.5, fontweight="bold", color=_NAVY,
        fontfamily="sans-serif",
    )
    fig.add_artist(plt.Line2D(
        [0.05, 0.95], [y - 0.004, y - 0.004],
        color=_MGRAY, linewidth=0.6, transform=fig.transFigure,
    ))


def _render_table(ax: plt.Axes, df: pd.DataFrame | None) -> None:
    """Render a DataFrame as a compact, styled matplotlib table."""
    ax.axis("off")
    if df is None or df.empty:
        ax.text(
            0.5, 0.5, "No data available",
            ha="center", va="center", fontsize=7, color="gray",
        )
        return

    # Truncate long cell values for readability
    display = df.copy()
    for col in display.columns:
        display[col] = display[col].astype(str).str[:18]

    tbl = ax.table(
        cellText=display.values.tolist(),
        colLabels=list(display.columns),
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(4.5)
    tbl.scale(1, 0.95)
    tbl.auto_set_column_width(list(range(len(display.columns))))

    for (row, col), cell in tbl.get_celld().items():
        cell.set_linewidth(0.2)
        cell.set_edgecolor(_MGRAY)
        if row == 0:                       # header row
            cell.set_facecolor(_NAVY)
            cell.set_text_props(color="white", fontweight="bold", fontsize=5)
        elif row % 2 == 0:                 # alternating stripe
            cell.set_facecolor(_LGRAY)
        else:
            cell.set_facecolor("white")


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF orchestration
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_pdf(
    name: str,
    player: pd.Series,
    season_stats: pd.DataFrame | None,
    pitch_data: pd.DataFrame | None,
    pitch_tag: str,
) -> str:
    """Build a single-page scouting-report PDF and return its file path.

    Steps
    -----
    1. Filter pitch data & compute the split table  (→ ``compute_pitch_split``)
    2. Build Plotly scatter figures                  (→ ``build_scatter``)
    3. Convert every Plotly figure to a raster image (→ ``_plotly_to_image``)
    4. Compose a matplotlib figure and save to PDF
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_path: str = tmp.name
    tmp.close()

    has_pitches = pitch_data is not None and not pitch_data.empty

    # ── 1. Filter pitch data & compute split table ────────────────────────
    filtered: pd.DataFrame | None = None
    split_df: pd.DataFrame | None = None
    if has_pitches:
        filtered = pitch_data.copy()
        if pitch_tag in filtered.columns:
            filtered = filtered.dropna(subset=[pitch_tag])
            filtered = filtered[filtered[pitch_tag] != "Undefined"]
        split_df = compute_pitch_split(filtered, pitch_tag)

    # ── 2–3. Pre-render all Plotly scatter charts to raster images ────────
    scatter_images: list[np.ndarray | None] = []
    if has_pitches and filtered is not None and not filtered.empty:
        for x_col, y_col in _SCATTER_PAIRS:
            pfig = build_scatter(filtered, x_col, y_col, pitch_tag)
            pfig.update_layout(margin=dict(l=40, r=10, t=28, b=40))
            scatter_images.append(_plotly_to_image(pfig, width=290, height=220))

    # ── 4. Download photo & compose PDF ──────────────────────────────────
    photo = _download_photo(player.get("photo", ""))

    with PdfPages(output_path) as pdf:
        _build_page(
            pdf,
            name=name,
            player=player,
            photo=photo,
            season_stats=season_stats,
            split_df=split_df,
            scatter_images=scatter_images,
            has_pitches=has_pitches,
        )

    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
#  Page layout
# ═══════════════════════════════════════════════════════════════════════════════

def _build_page(
    pdf: PdfPages,
    *,
    name: str,
    player: pd.Series,
    photo: Image.Image | None,
    season_stats: pd.DataFrame | None,
    split_df: pd.DataFrame | None,
    scatter_images: list[np.ndarray | None],
    has_pitches: bool,
) -> None:
    """
    Compose ONE portrait-letter page (8.5 × 11 in).

    ┌──────────────────────────────────────┐
    │  ██  {Name} — Pitching Report  ██   │  banner
    ├──────────────────────────────────────┤
    │  PITCHER INFORMATION  │ SEASON STATS │  row 0
    │  [Photo] [Bio text]   │ [stats tbl]  │
    ├──────────────────────────────────────┤
    │  PITCH MOVEMENT                      │  row 1
    │  [scatter 1] [scatter 2] [scatter 3] │
    ├──────────────────────────────────────┤
    │  PITCH USAGE BY COUNT                │  row 2
    │  [split table]                       │
    └──────────────────────────────────────┘
    """
    fig = plt.figure(figsize=(8.5, 11), facecolor="white")
    _draw_banner(fig, name)

    # Three content rows, tightly packed
    gs = fig.add_gridspec(
        nrows=3, ncols=1,
        height_ratios=[1.2, 1.8, 1.6],
        hspace=0.08,
        top=0.925, bottom=0.02, left=0.05, right=0.95,
    )

    _layout_pitcher_and_stats(fig, gs[0], player, photo, season_stats)
    _layout_scatter_plots(fig, gs[1], scatter_images, has_pitches)
    _layout_split_table(fig, gs[2], split_df)
    _draw_footer(fig)

    pdf.savefig(fig)
    plt.close(fig)


# ── Row helpers ───────────────────────────────────────────────────────────────

def _layout_pitcher_and_stats(
    fig: plt.Figure,
    gs_slot,
    player: pd.Series,
    photo: Image.Image | None,
    season_stats: pd.DataFrame | None,
) -> None:
    """Row 0 — pitcher photo + bio (left) and season-stats table (right)."""
    row = gs_slot.subgridspec(1, 2, wspace=0.08, width_ratios=[1.1, 1.6])

    # ── Left half: photo + bio ────────────────────────────────────────────
    left = row[0, 0].subgridspec(1, 2, wspace=0.06, width_ratios=[1, 1.8])

    bb_left = row[0, 0].get_position(fig)
    _section_label(fig, bb_left.y1 + 0.008, "PITCHER INFORMATION")

    # Photo
    ax_photo = fig.add_subplot(left[0, 0])
    ax_photo.axis("off")
    if photo is not None:
        ax_photo.imshow(photo, aspect="auto")
        for sp in ax_photo.spines.values():
            sp.set_visible(True)
            sp.set_color(_MGRAY)
            sp.set_linewidth(0.8)
    else:
        ax_photo.set_facecolor(_LGRAY)
        ax_photo.text(
            0.5, 0.5, "No photo",
            ha="center", va="center", fontsize=7, color="gray",
            transform=ax_photo.transAxes,
        )

    # Bio fields
    ax_bio = fig.add_subplot(left[0, 1])
    ax_bio.axis("off")

    bio_fields = [
        ("Name",   player.get("full_name", "")),
        ("Team",   player.get("teamname", "")),
        ("Throws", player.get("throws", "")),
        ("Bats",   player.get("bats", "")),
        ("Ht/Wt", f"{player.get('height', '')} / {player.get('weight', '')}"),
        ("From",   player.get("hometown", "")),
    ]
    y = 0.92
    for label, value in bio_fields:
        if not value or value.strip() == "/":
            continue
        ax_bio.text(
            0.02, y, f"{label}:",
            transform=ax_bio.transAxes,
            fontsize=6, fontweight="bold", color=_NAVY,
            fontfamily="sans-serif", va="top",
        )
        ax_bio.text(
            0.28, y, str(value),
            transform=ax_bio.transAxes,
            fontsize=6, color="#333", fontfamily="sans-serif", va="top",
        )
        y -= 0.15

    # ── Right half: season stats table ────────────────────────────────────
    bb_right = row[0, 1].get_position(fig)
    fig.text(
        bb_right.x0 + 0.01, bb_right.y1 + 0.008,
        "SEASON STATS",
        fontsize=7.5, fontweight="bold", color=_NAVY,
        fontfamily="sans-serif",
    )

    ax_stats = fig.add_subplot(row[0, 1])
    _render_table(ax_stats, season_stats)


def _layout_scatter_plots(
    fig: plt.Figure,
    gs_slot,
    scatter_images: list[np.ndarray | None],
    has_pitches: bool,
) -> None:
    """Row 1 — three scatter-plot images side by side."""
    bb = gs_slot.get_position(fig)
    _section_label(fig, bb.y1 + 0.008, "PITCH MOVEMENT")

    sub = gs_slot.subgridspec(1, 3, wspace=0.02)
    for j in range(3):
        ax = fig.add_subplot(sub[0, j])
        ax.axis("off")

        if j < len(scatter_images) and scatter_images[j] is not None:
            ax.imshow(scatter_images[j])
        elif has_pitches:
            ax.text(
                0.5, 0.5,
                "Install kaleido to\nenable chart export",
                ha="center", va="center", fontsize=6, color="gray",
                transform=ax.transAxes,
            )
        else:
            ax.text(
                0.5, 0.5, "No pitch data",
                ha="center", va="center", fontsize=6, color="gray",
                transform=ax.transAxes,
            )


def _layout_split_table(
    fig: plt.Figure,
    gs_slot,
    split_df: pd.DataFrame | None,
) -> None:
    """Row 2 — pitch-usage-by-count table."""
    bb = gs_slot.get_position(fig)
    _section_label(fig, bb.y1 + 0.008, "PITCH USAGE BY COUNT")

    ax = fig.add_subplot(gs_slot)
    _render_table(ax, split_df)


def _draw_footer(fig: plt.Figure) -> None:
    """Subtle italic footer at the very bottom of the page."""
    fig.text(
        0.5, 0.005,
        "Generated by SLUGGER Pitching Widget",
        ha="center", fontsize=5, color="#aaa",
        fontfamily="sans-serif", style="italic",
    )
