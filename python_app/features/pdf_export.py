"""
PDF scouting report export (single-player and team multi-page).

Callback : triggered by either PDF button in the toolbar.
Pipeline : pre-render Plotly figures → convert to raster images via kaleido
           → compose everything onto matplotlib page(s) → save as PDF.

Every chart and table reuses the **same public functions** that drive the
Dash UI — nothing is re-implemented here:

    scatter_plots.build_scatter()      → pitch-movement scatter charts
    heatmaps.build_heatmap()           → strike-zone heatmaps
    pitch_split.compute_pitch_split()  → count-based pitch-usage table
"""

from __future__ import annotations

import io
import tempfile
import traceback
import textwrap
from datetime import date
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")                          # headless backend — no GUI

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
import requests
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image

from dash import Input, Output, State, callback, ctx, dcc, no_update

from python_app.config import TABLE_HEADER_COLOR
from python_app.features.heatmaps import build_heatmap
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
_BORDER: str = "#c8c9cc"
_HILITE: str = "#E6EEF9"

# Scatter-plot column pairs shown in the PDF (x, y) — 2 charts
_SCATTER_PAIRS: list[tuple[str, str]] = [
    ("rel_speed",  "induced_vert_break"),
    ("horz_break", "induced_vert_break"),
]

# Human-readable chart titles for each scatter pair
_SCATTER_TITLES: list[str] = [
    "Vertical Break vs Velocity",
    "Induced Vertical Break vs Horizontal Break",
]

_HEATMAP_TITLES: list[str] = [
    "Pitch map vs RH Batters",
    "Pitch map vs LH Batters",
]
_ALL_TEAMS = "__ALL_TEAMS__"

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
    Input("download-team-pdf-btn", "n_clicks"),
    State("selected-player", "value"),
    State("selected-team", "value"),
    State("pitch-data-store", "data"),
    State("tag-choice", "value"),
    prevent_initial_call=True,
)
def download_pdf(
    player_clicks: int | None,
    team_clicks: int | None,
    selected_playerlinkid: str | None,
    selected_team: str | None,
    pitch_records: list[dict] | None,
    tag: str | None,
):
    """Generate and send either a player PDF or a team multi-page PDF."""
    try:
        pitch_tag = tag or "auto_pitch_type"
        triggered = ctx.triggered_id

        if triggered == "download-pdf-btn":
            if not player_clicks or not selected_playerlinkid:
                return no_update
            player = cache.get_player(selected_playerlinkid)
            if player is None:
                return no_update

            selected_name = str(player.get("full_name", "")).strip() or "Pitcher"
            stats = cache.get_season_stats(str(player["playerlinkid"]))
            pitch_df = pd.DataFrame(pitch_records) if pitch_records else None

            pdf_path = _generate_pdf(selected_name, player, stats, pitch_df, pitch_tag)
            filename = f"{_safe_filename(selected_name)} Pitcher Report.pdf"
            return dcc.send_file(pdf_path, filename=filename)

        if triggered == "download-team-pdf-btn":
            if not team_clicks or not selected_team or selected_team == _ALL_TEAMS:
                return no_update
            team_players = cache.get_players(selected_team)
            if team_players.empty:
                return no_update

            pdf_path = _generate_team_pdf(team_players, pitch_tag)
            filename = f"{_safe_filename(selected_team)} Pitching Reports.pdf"
            return dcc.send_file(pdf_path, filename=filename)

        return no_update
    except Exception:
        traceback.print_exc()
        return no_update


def _safe_filename(raw: str) -> str:
    """Keep filenames readable and filesystem-safe."""
    cleaned = "".join(ch for ch in str(raw) if ch.isalnum() or ch in {" ", "_", "-"})
    return " ".join(cleaned.split()).strip() or "Report"


def _team_sorted(players: pd.DataFrame) -> pd.DataFrame:
    """De-duplicate then sort players for team exports."""
    if players.empty:
        return players

    deduped = players.copy()
    deduped["playerlinkid"] = deduped["playerlinkid"].fillna("").astype(str).str.strip()
    deduped["full_name"] = deduped["full_name"].fillna("").astype(str).str.strip()

    with_id = deduped[deduped["playerlinkid"] != ""]
    no_id = deduped[deduped["playerlinkid"] == ""]

    with_id = with_id.drop_duplicates(subset=["playerlinkid"], keep="first")
    no_id = no_id.drop_duplicates(subset=["full_name"], keep="first")

    unique_players = pd.concat([with_id, no_id], ignore_index=True)
    return unique_players.sort_values(
        ["lname", "fname", "full_name", "playerlinkid"],
        na_position="last",
    )


def _pitch_df_for_player(player: pd.Series) -> pd.DataFrame | None:
    """Fetch ALPB pitch-level data for one player."""
    playerlinkid = str(player.get("playerlinkid", "")).strip()
    if not playerlinkid:
        return None
    alpb_id = cache.get_alpb_id(playerlinkid)
    if not alpb_id:
        return None
    records = cache.get_pitch_data(alpb_id)
    if not records:
        return None
    return pd.DataFrame(records)


# ═══════════════════════════════════════════════════════════════════════════════
#  Image / download helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _plotly_to_image(
    fig: go.Figure,
    width: int = 520,
    height: int = 380,
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
        fontsize=12.5, fontweight="bold", color="white",
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
        0.04, y, text,
        fontsize=8, fontweight="bold", color=_NAVY,
        fontfamily="sans-serif",
    )


def _draw_navy_header(
    fig: plt.Figure, x0: float, y0: float, w: float, h: float, title: str,
) -> None:
    """Draw a navy header bar at the given figure position."""
    ax = fig.add_axes([x0, y0, w, h])
    ax.set_facecolor(_NAVY)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(
        0.5, 0.5, title,
        ha="center", va="center",
        fontsize=7.5, fontweight="bold", color="white",
        fontfamily="sans-serif",
    )
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


def _render_table(
    ax: plt.Axes,
    df: pd.DataFrame | None,
    fontsize: float = 5.5,
    *,
    fill_bbox: bool = False,
    highlight_row_max: bool = False,
    uppercase_headers: bool = False,
) -> None:
    """Render a DataFrame as a compact, styled matplotlib table."""
    ax.axis("off")
    if df is None or df.empty:
        ax.text(
            0.5, 0.5, "No data available",
            ha="center", va="center", fontsize=7, color="gray",
        )
        return

    display = df.copy()
    if uppercase_headers:
        display.columns = [str(c).upper() for c in display.columns]
    for col in display.columns:
        display[col] = display[col].astype(str).str[:24]

    # Weight wider columns (long headers / values) so the table fills the card
    # proportionally instead of collapsing to the centre.
    col_widths: list[float] = []
    for col in display.columns:
        max_cell_len = display[col].astype(str).str.len().max()
        header_len = len(str(col))
        weight = max(3, int(max(max_cell_len, header_len)))
        col_widths.append(float(weight))
    total_width = sum(col_widths) or 1.0
    col_widths = [w / total_width for w in col_widths]

    table_kwargs = {}
    if fill_bbox:
        table_kwargs["bbox"] = [0.0, 0.0, 1.0, 1.0]

    tbl = ax.table(
        cellText=display.values.tolist(),
        colLabels=list(display.columns),
        loc="center" if fill_bbox else "upper center",
        cellLoc="center",
        colWidths=col_widths,
        **table_kwargs,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    if not fill_bbox:
        tbl.scale(1, 1.08)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_linewidth(0.3)
        cell.set_edgecolor(_MGRAY)
        if row == 0:
            cell.set_facecolor(_NAVY)
            cell.set_text_props(color="white", fontweight="bold", fontsize=fontsize)
        elif row % 2 == 0:
            cell.set_facecolor(_LGRAY)
        else:
            cell.set_facecolor("white")

    if highlight_row_max and len(display.columns) > 1:
        for row_idx in range(len(df)):
            numeric_vals: list[tuple[int, float]] = []
            for col_idx in range(1, len(df.columns)):
                val = pd.to_numeric(df.iloc[row_idx, col_idx], errors="coerce")
                if pd.notna(val):
                    numeric_vals.append((col_idx, float(val)))
            if not numeric_vals:
                continue

            max_val = max(v for _, v in numeric_vals)
            for col_idx, val in numeric_vals:
                if abs(val - max_val) > 1e-9:
                    continue
                cell = tbl[(row_idx + 1, col_idx)]
                cell.set_facecolor(_HILITE)
                cell.set_text_props(color=_NAVY, fontweight="bold", fontsize=fontsize)


def _draw_bordered_rect(
    fig: plt.Figure, x0: float, y0: float, w: float, h: float,
) -> None:
    """Draw a light-bordered rectangle on the figure (card outline)."""
    rect = patches.FancyBboxPatch(
        (x0, y0), w, h,
        boxstyle="round,pad=0.003",
        facecolor="white", edgecolor=_BORDER, linewidth=0.8,
        transform=fig.transFigure, zorder=-1,
    )
    fig.patches.append(rect)


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
    """Build a single-player scouting-report PDF and return its file path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_path: str = tmp.name
    tmp.close()

    with PdfPages(output_path) as pdf:
        _append_player_page(
            pdf=pdf,
            name=name,
            player=player,
            season_stats=season_stats,
            pitch_data=pitch_data,
            pitch_tag=pitch_tag,
        )

    return output_path


def _generate_team_pdf(
    team_players: pd.DataFrame,
    pitch_tag: str,
) -> str:
    """Build a team multi-page PDF (one player per page)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_path: str = tmp.name
    tmp.close()

    with PdfPages(output_path) as pdf:
        for _, player in _team_sorted(team_players).iterrows():
            name = str(player.get("full_name", "")).strip() or "Pitcher"
            playerlinkid = str(player.get("playerlinkid", "")).strip()
            stats = cache.get_season_stats(playerlinkid) if playerlinkid else None
            pitch_df = _pitch_df_for_player(player)
            _append_player_page(
                pdf=pdf,
                name=name,
                player=player,
                season_stats=stats,
                pitch_data=pitch_df,
                pitch_tag=pitch_tag,
            )

    return output_path


def _append_player_page(
    *,
    pdf: PdfPages,
    name: str,
    player: pd.Series,
    season_stats: pd.DataFrame | None,
    pitch_data: pd.DataFrame | None,
    pitch_tag: str,
) -> None:
    """Assemble charts/tables and append exactly one player page to a PDF."""
    has_pitches = pitch_data is not None and not pitch_data.empty

    filtered: pd.DataFrame | None = None
    split_df: pd.DataFrame | None = None
    if has_pitches:
        filtered = pitch_data.copy()
        if pitch_tag in filtered.columns:
            filtered = filtered.dropna(subset=[pitch_tag])
            filtered = filtered[filtered[pitch_tag] != "Undefined"]
        split_df = compute_pitch_split(filtered, pitch_tag)

    scatter_images: list[np.ndarray | None] = []
    heatmap_images: list[np.ndarray | None] = []
    if has_pitches and filtered is not None and not filtered.empty:
        for x_col, y_col in _SCATTER_PAIRS:
            pfig = build_scatter(filtered, x_col, y_col, pitch_tag)
            pfig.update_layout(margin=dict(l=50, r=10, t=10, b=40), height=260)
            scatter_images.append(_plotly_to_image(pfig, width=620, height=360))

        rh_df = _filter_by_batter_side(filtered, "Right")
        lh_df = _filter_by_batter_side(filtered, "Left")
        for side_df in [rh_df, lh_df]:
            hfig = build_heatmap(side_df)
            hfig.update_layout(margin=dict(l=10, r=10, t=20, b=10), height=250)
            heatmap_images.append(_plotly_to_image(hfig, width=620, height=340))

    photo = _download_photo(player.get("photo", ""))
    _build_page(
        pdf,
        name=name,
        player=player,
        photo=photo,
        season_stats=season_stats,
        split_df=split_df,
        scatter_images=scatter_images,
        heatmap_images=heatmap_images,
        has_pitches=has_pitches,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Page layout — dedicated export template (all coordinates in [0, 1])
# ═══════════════════════════════════════════════════════════════════════════════

_HDR = 0.021          # navy card-header height
_PAD = 0.005          # inner padding
_LR  = 0.035          # left/right page margin
_GAP = 0.012          # horizontal gap between cards


def _filter_by_batter_side(df: pd.DataFrame, side: str) -> pd.DataFrame:
    if "batter_side" not in df.columns:
        return pd.DataFrame()
    return df[df["batter_side"] == side]


def _render_chart_card(
    fig: plt.Figure,
    *,
    x0: float,
    y0: float,
    w: float,
    h: float,
    title: str,
    image: np.ndarray | None,
    empty_text: str,
) -> None:
    _draw_bordered_rect(fig, x0, y0, w, h)

    hdr_y = y0 + h - _HDR
    _draw_navy_header(fig, x0, hdr_y, w, _HDR, title)
    fig.add_artist(plt.Line2D(
        [x0, x0 + w], [hdr_y, hdr_y],
        color=_RED, linewidth=1.4,
        transform=fig.transFigure, zorder=5,
    ))

    ax = fig.add_axes([x0 + _PAD, y0 + _PAD, w - 2 * _PAD, h - _HDR - 2 * _PAD])
    ax.axis("off")
    if image is not None:
        ax.imshow(image)
    else:
        ax.text(
            0.5,
            0.5,
            empty_text,
            ha="center",
            va="center",
            fontsize=7,
            color="gray",
            transform=ax.transAxes,
        )


def _build_page(
    pdf: PdfPages,
    *,
    name: str,
    player: pd.Series,
    photo: Image.Image | None,
    season_stats: pd.DataFrame | None,
    split_df: pd.DataFrame | None,
    scatter_images: list[np.ndarray | None],
    heatmap_images: list[np.ndarray | None],
    has_pitches: bool,
) -> None:
    fig = plt.figure(figsize=(8.5, 11), facecolor="white")
    _draw_banner(fig, name)

    page_w = 1.0 - 2 * _LR

    # ── Row 0: Pitcher Info + Season Stats ────────────────────────────────
    r0_label = 0.925
    r0_top = 0.912
    r0_bot = 0.730
    r0_h = r0_top - r0_bot

    _section_label(fig, r0_label, "PITCHER INFORMATION & SEASON STATS")

    lw = page_w * 0.36
    rw = page_w - lw - _GAP
    lx = _LR
    rx = lx + lw + _GAP

    _draw_bordered_rect(fig, lx, r0_bot, lw, r0_h)
    _draw_bordered_rect(fig, rx, r0_bot, rw, r0_h)
    _layout_pitcher_card(fig, lx, r0_bot, lw, r0_h, player, photo)
    _layout_stats_card(fig, rx, r0_bot, rw, r0_h, season_stats)

    # ── Row 1: Pitch Movement (2 scatter charts) ──────────────────────────
    r1_label = 0.710
    r1_top = 0.698
    r1_bot = 0.510
    r1_h = r1_top - r1_bot

    _section_label(fig, r1_label, "PITCH MOVEMENT")

    cw = (page_w - _GAP) / 2
    cx1 = _LR
    cx2 = _LR + cw + _GAP

    _render_chart_card(
        fig,
        x0=cx1,
        y0=r1_bot,
        w=cw,
        h=r1_h,
        title=_SCATTER_TITLES[0],
        image=scatter_images[0] if len(scatter_images) > 0 else None,
        empty_text=(
            "Install kaleido to\nenable chart export"
            if has_pitches else "No pitch data"
        ),
    )
    _render_chart_card(
        fig,
        x0=cx2,
        y0=r1_bot,
        w=cw,
        h=r1_h,
        title=_SCATTER_TITLES[1],
        image=scatter_images[1] if len(scatter_images) > 1 else None,
        empty_text=(
            "Install kaleido to\nenable chart export"
            if has_pitches else "No pitch data"
        ),
    )

    # ── Row 2: Pitch Heatmaps (2 charts) ──────────────────────────────────
    r2_label = 0.495
    r2_top = 0.483
    r2_bot = 0.295
    r2_h = r2_top - r2_bot

    _section_label(fig, r2_label, "PITCH HEATMAPS")

    _render_chart_card(
        fig,
        x0=cx1,
        y0=r2_bot,
        w=cw,
        h=r2_h,
        title=_HEATMAP_TITLES[0],
        image=heatmap_images[0] if len(heatmap_images) > 0 else None,
        empty_text=(
            "Install kaleido to\nenable chart export"
            if has_pitches else "No pitch data"
        ),
    )
    _render_chart_card(
        fig,
        x0=cx2,
        y0=r2_bot,
        w=cw,
        h=r2_h,
        title=_HEATMAP_TITLES[1],
        image=heatmap_images[1] if len(heatmap_images) > 1 else None,
        empty_text=(
            "Install kaleido to\nenable chart export"
            if has_pitches else "No pitch data"
        ),
    )

    # ── Row 3: Pitch Usage table ───────────────────────────────────────────
    r3_label = 0.280
    r3_top = 0.268
    r3_bot = 0.045

    _section_label(fig, r3_label, "PITCH USAGE BY COUNT")
    split_x = 0.02
    split_w = 0.96
    _draw_bordered_rect(fig, split_x, r3_bot, split_w, r3_top - r3_bot)
    ax_split = fig.add_axes([
        split_x + _PAD, r3_bot + _PAD,
        split_w - 2 * _PAD, r3_top - r3_bot - 2 * _PAD,
    ])
    _render_table(
        ax_split,
        split_df,
        fontsize=5.2,
        fill_bbox=True,
        highlight_row_max=True,
    )

    _draw_footer(fig)
    pdf.savefig(fig)
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
#  Row 0 helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _layout_pitcher_card(
    fig: plt.Figure,
    x0: float, y0: float, w: float, h: float,
    player: pd.Series,
    photo: Image.Image | None,
) -> None:
    """Pitcher Information card: navy header → photo (left) + centred bio (right)."""
    _draw_navy_header(fig, x0, y0 + h - _HDR, w, _HDR, "Pitcher Information")

    cy0 = y0 + _PAD
    ch  = h - _HDR - 2 * _PAD

    # Photo — left ~40 %
    pw = w * 0.38
    ax_photo = fig.add_axes([x0 + _PAD, cy0, pw, ch])
    ax_photo.axis("off")
    ax_photo.set_facecolor(_LGRAY)
    if photo is not None:
        # Convert PIL Image → RGBA numpy array so matplotlib renders
        # colour correctly (palette-mode GIFs would otherwise be blank).
        arr = np.asarray(photo.convert("RGBA"))
        ax_photo.imshow(arr, aspect="equal")
        ax_photo.set_anchor("C")
        for sp in ax_photo.spines.values():
            sp.set_visible(True)
            sp.set_color(_MGRAY)
            sp.set_linewidth(0.8)
    else:
        ax_photo.text(0.5, 0.5, "No photo",
                      ha="center", va="center", fontsize=7, color="gray",
                      transform=ax_photo.transAxes)

    # Bio — right portion, wrapped to stay within the card.
    bio_left  = x0 + _PAD + pw + 0.008
    bio_right = x0 + w - _PAD
    ax_bio = fig.add_axes([bio_left, cy0, bio_right - bio_left, ch])
    ax_bio.axis("off")

    fields = [
        ("Name",     player.get("full_name", "")),
        ("Team",     player.get("teamname", "")),
        ("Throws",   player.get("throws", "")),
        ("Bats",     player.get("bats", "")),
        ("Height",   player.get("height", "")),
        ("Weight",   str(player.get("weight", ""))),
        ("Hometown", player.get("hometown", "")),
    ]
    valid = [(label, str(value).strip()) for label, value in fields
             if value and str(value).strip() and str(value).strip() != "/"]
    if not valid:
        ax_bio.text(
            0.02, 0.5, "No player info",
            ha="left", va="center", fontsize=6.2, color="gray",
            transform=ax_bio.transAxes,
        )
        return

    rendered_lines: list[tuple[str, str, bool]] = []
    for label, value in valid:
        wrapped = textwrap.wrap(value, width=18) or [value]
        rendered_lines.append((f"{label}:", wrapped[0], True))
        for cont in wrapped[1:]:
            rendered_lines.append(("", cont, False))

    max_lines = 11
    if len(rendered_lines) > max_lines:
        rendered_lines = rendered_lines[:max_lines]
        last_label, last_value, last_main = rendered_lines[-1]
        rendered_lines[-1] = (
            last_label,
            (last_value[:21] + "…") if len(last_value) > 21 else (last_value + "…"),
            last_main,
        )

    top_margin = 0.08
    bottom_margin = 0.06
    usable_h = 1.0 - top_margin - bottom_margin
    line_step = usable_h / max(1, len(rendered_lines))
    y = 1.0 - top_margin

    for label, value, main_line in rendered_lines:
        if main_line:
            ax_bio.text(
                0.04, y, label,
                ha="left", va="center",
                fontsize=6.1, fontweight="bold", color=_NAVY,
                transform=ax_bio.transAxes,
            )
            ax_bio.text(
                0.48, y, value,
                ha="left", va="center",
                fontsize=6.1, color="#333",
                transform=ax_bio.transAxes,
            )
        else:
            ax_bio.text(
                0.48, y, value,
                ha="left", va="center",
                fontsize=6.0, color="#333",
                transform=ax_bio.transAxes,
            )
        y -= line_step


def _layout_stats_card(
    fig: plt.Figure,
    x0: float, y0: float, w: float, h: float,
    season_stats: pd.DataFrame | None,
) -> None:
    """Season Stats card: navy header → stats table."""
    _draw_navy_header(fig, x0, y0 + h - _HDR, w, _HDR, "Season Stats")

    ax = fig.add_axes([x0 + _PAD, y0 + _PAD, w - 2 * _PAD, h - _HDR - 2 * _PAD])
    _render_table(
        ax,
        season_stats,
        fontsize=6,
        fill_bbox=True,
        uppercase_headers=True,
    )


def _draw_footer(fig: plt.Figure) -> None:
    fig.text(
        0.5, 0.008,
        "Generated by SLUGGER Pitching Widget",
        ha="center", fontsize=5, color="#aaa",
        fontfamily="sans-serif", style="italic",
    )
