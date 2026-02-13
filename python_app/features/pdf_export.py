"""
PDF scouting report export.

Callback: triggered by the Download PDF button.
Generation: builds a portrait letter-size (8.5 × 11) scouting report by
converting Plotly visualizations from the feature modules into images
and composing them with matplotlib.

Uses the same public methods that power the Dash UI:
  - scatter_plots.build_scatter()      → pitch movement charts
  - heatmaps.build_heatmap()           → strike-zone density maps
  - pitch_split.compute_pitch_split()  → count-based usage table
"""

import io
import tempfile
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
import requests
from PIL import Image

from dash import dcc, callback, Input, Output, State, no_update

from python_app.config import TABLE_HEADER_COLOR
from python_app.lib.cache import cache
from python_app.features.scatter_plots import build_scatter
from python_app.features.heatmaps import build_heatmap
from python_app.features.pitch_split import compute_pitch_split

# ── Color palette ────────────────────────────────────────────────────────────
_NAVY    = TABLE_HEADER_COLOR   # "#002D72"
_RED     = "#C8102E"
_LGRAY   = "#f5f6fa"
_MGRAY   = "#dcdde1"


# ── Callback ─────────────────────────────────────────────────────────────────

@callback(
    Output("download-pdf", "data"),
    Input("download-pdf-btn", "n_clicks"),
    State("selected-player", "value"),
    State("pitch-data-store", "data"),
    State("tag-choice", "value"),
    prevent_initial_call=True,
)
def download_pdf(n_clicks, selected_name, pitch_records, tag):
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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _plotly_to_image(fig, width=450, height=320, scale=2):
    """Convert a Plotly figure to a numpy image array for matplotlib."""
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=scale)
    return plt.imread(io.BytesIO(img_bytes))


def _download_photo(url):
    """Download a player photo from *url* and return a PIL Image (or None)."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content))
    except Exception:
        return None


def _draw_banner(fig, name):
    """Draw a dark navy header banner with player name and date."""
    ax = fig.add_axes([0, 0.93, 1, 0.07])
    ax.set_facecolor(_NAVY)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.5, 0.58, f"{name}  —  Pitching Report",
            ha="center", va="center",
            fontsize=17, fontweight="bold", color="white",
            fontfamily="sans-serif")
    ax.text(0.5, 0.15, date.today().strftime("%B %d, %Y"),
            ha="center", va="center",
            fontsize=8, color="#8eafd4", fontfamily="sans-serif")
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    # Red accent line
    fig.add_artist(plt.Line2D(
        [0, 1], [0.93, 0.93],
        color=_RED, linewidth=2.5, transform=fig.transFigure, zorder=5,
    ))


def _draw_section_label(fig, y, text):
    """Draw a small section header label at figure-coordinate *y*."""
    fig.text(0.06, y, text,
             fontsize=8.5, fontweight="bold", color=_NAVY,
             fontfamily="sans-serif")
    fig.add_artist(plt.Line2D(
        [0.05, 0.95], [y - 0.005, y - 0.005],
        color=_MGRAY, linewidth=0.7, transform=fig.transFigure,
    ))


def _render_table(ax, df, title=""):
    """Render a pandas DataFrame as a styled matplotlib table on *ax*."""
    ax.axis("off")
    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data available",
                ha="center", va="center", fontsize=8, color="gray")
        return

    display_df = df.copy()
    for col in display_df.columns:
        display_df[col] = display_df[col].astype(str).str[:18]

    tbl = ax.table(
        cellText=display_df.values.tolist(),
        colLabels=list(display_df.columns),
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(5)
    tbl.scale(1, 1.05)
    tbl.auto_set_column_width(list(range(len(display_df.columns))))

    for (row, col), cell in tbl.get_celld().items():
        cell.set_linewidth(0.25)
        cell.set_edgecolor(_MGRAY)
        if row == 0:
            cell.set_facecolor(_NAVY)
            cell.set_text_props(color="white", fontweight="bold", fontsize=5.5)
        elif row % 2 == 0:
            cell.set_facecolor(_LGRAY)
        else:
            cell.set_facecolor("white")


# ── PDF generation ───────────────────────────────────────────────────────────

def _generate_pdf(name, player, season_stats, pitch_data, pitch_tag):
    """Build a scouting report PDF and return the file path."""
    output_path = tempfile.mktemp(suffix=".pdf")
    has_stats = season_stats is not None and not season_stats.empty
    has_pitches = pitch_data is not None and not pitch_data.empty

    # Prepare pitch data
    filtered = None
    split_df = None
    pitch_types = []
    if has_pitches:
        filtered = pitch_data.copy()
        if pitch_tag in filtered.columns:
            filtered = filtered.dropna(subset=[pitch_tag])
            filtered = filtered[filtered[pitch_tag] != "Undefined"]
        split_df = compute_pitch_split(filtered, pitch_tag)
        if pitch_tag in filtered.columns:
            pitch_types = sorted(
                t for t in filtered[pitch_tag].dropna().unique()
                if t != "Undefined"
            )

    # Download player photo
    photo = _download_photo(player.get("photo", ""))

    with PdfPages(output_path) as pdf:
        _build_main_page(
            pdf, name, player, photo,
            has_stats, season_stats,
            has_pitches, filtered, split_df, pitch_tag,
        )
        if has_pitches and pitch_types:
            _build_heatmap_pages(pdf, name, filtered, pitch_tag, pitch_types)

    return output_path


# ── Page 1 ───────────────────────────────────────────────────────────────────

def _build_main_page(
    pdf, name, player, photo,
    has_stats, season_stats,
    has_pitches, filtered, split_df, pitch_tag,
):
    """
    Portrait letter page (8.5 × 11 in):

    ┌──────────────────────────────────┐
    │  ██  {Name} — Pitching Report ██ │  banner
    │  ═══════════════════════════════  │  accent line
    │                                  │
    │  PITCHER INFORMATION             │  section label
    │  ┌───────┬───────────────────┐   │
    │  │ Photo │  Bio   │  Season  │   │
    │  │       │  Info  │  Stats   │   │
    │  └───────┴───────────────────┘   │
    │                                  │
    │  PITCH MOVEMENT                  │  section label
    │  ┌──────┬──────┬──────┐          │
    │  │ sc 1 │ sc 2 │ sc 3 │          │
    │  └──────┴──────┴──────┘          │
    │                                  │
    │  PITCH USAGE BY COUNT            │  section label
    │  ┌────────────────────────────┐  │
    │  │  split table               │  │
    │  └────────────────────────────┘  │
    └──────────────────────────────────┘
    """
    fig = plt.figure(figsize=(8.5, 11), facecolor="white")

    # ── Banner ────────────────────────────────────────────────────────────
    _draw_banner(fig, name)

    # ── Content grid (3 rows) ─────────────────────────────────────────────
    gs = fig.add_gridspec(
        nrows=3, ncols=1,
        height_ratios=[1.4, 2.8, 1.8],
        hspace=0.22,
        top=0.895, bottom=0.025, left=0.05, right=0.95,
    )

    # ── Row 0 — Pitcher info  ─────────────────────────────────────────────
    _draw_section_label(fig, 0.905, "PITCHER INFORMATION")

    top = gs[0].subgridspec(
        1, 3, wspace=0.08, width_ratios=[0.8, 1.0, 3.0],
    )

    # Photo
    ax_photo = fig.add_subplot(top[0, 0])
    ax_photo.axis("off")
    if photo is not None:
        ax_photo.imshow(photo, aspect="equal")
        for sp in ax_photo.spines.values():
            sp.set_visible(True)
            sp.set_color(_MGRAY)
            sp.set_linewidth(1)
    else:
        ax_photo.set_facecolor(_LGRAY)
        ax_photo.text(0.5, 0.5, "No photo",
                      ha="center", va="center", fontsize=8, color="gray",
                      transform=ax_photo.transAxes)
        for sp in ax_photo.spines.values():
            sp.set_visible(True)
            sp.set_color(_MGRAY)
            sp.set_linewidth(0.5)

    # Bio info — compact single-line style
    ax_bio = fig.add_subplot(top[0, 1])
    ax_bio.axis("off")
    fields = [
        ("Name",     player.get("full_name", "")),
        ("Team",     player.get("teamname", "")),
        ("Throws",   player.get("throws", "")),
        ("Bats",     player.get("bats", "")),
        ("Height",   player.get("height", "")),
        ("Weight",   player.get("weight", "")),
        ("Hometown", player.get("hometown", "")),
    ]
    bio_lines = [f"{k}:  {v}" for k, v in fields if v]
    bio_text = "\n".join(bio_lines)
    ax_bio.text(0.05, 0.92, bio_text, transform=ax_bio.transAxes,
                fontsize=6, verticalalignment="top",
                fontfamily="sans-serif", color="#333333",
                linespacing=1.8,
                bbox=dict(boxstyle="round,pad=0.4", facecolor=_LGRAY,
                          edgecolor=_MGRAY, linewidth=0.5))

    # Season stats table
    ax_stats = fig.add_subplot(top[0, 2])
    _render_table(ax_stats, season_stats)

    # ── Row 1 — Scatter plots  ────────────────────────────────────────────
    # Section label y ≈ top of row 1 in figure coordinates
    _draw_section_label(fig, _row_top(gs, 1, fig), "PITCH MOVEMENT")

    if has_pitches and filtered is not None and not filtered.empty:
        scatter_gs = gs[1].subgridspec(1, 3, wspace=0.04)
        scatter_configs = [
            ("horz_break", "induced_vert_break"),
            ("rel_speed",  "induced_vert_break"),
            ("rel_speed",  "horz_break"),
        ]
        for j, (x_col, y_col) in enumerate(scatter_configs):
            ax = fig.add_subplot(scatter_gs[0, j])
            plotly_fig = build_scatter(filtered, x_col, y_col, pitch_tag)
            if plotly_fig.data:
                try:
                    img = _plotly_to_image(plotly_fig, width=340, height=260)
                    ax.imshow(img)
                except Exception:
                    ax.text(0.5, 0.5, "Chart unavailable",
                            ha="center", va="center", fontsize=7,
                            transform=ax.transAxes, color="gray")
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        fontsize=7, transform=ax.transAxes, color="gray")
            ax.axis("off")
    else:
        ax_no = fig.add_subplot(gs[1])
        ax_no.axis("off")
        ax_no.text(0.5, 0.5, "No pitch data available",
                   ha="center", va="center", fontsize=9, color="gray")

    # ── Row 2 — Pitch split table  ────────────────────────────────────────
    _draw_section_label(fig, _row_top(gs, 2, fig), "PITCH USAGE BY COUNT")

    ax_split = fig.add_subplot(gs[2])
    _render_table(ax_split, split_df)

    # ── Footer ────────────────────────────────────────────────────────────
    fig.add_artist(plt.Line2D(
        [0.05, 0.95], [0.018, 0.018],
        color=_MGRAY, linewidth=0.5, transform=fig.transFigure,
    ))
    fig.text(0.5, 0.007,
             "Generated by SLUGGER Pitching Widget",
             ha="center", fontsize=5.5, color="#aaaaaa",
             fontfamily="sans-serif", style="italic")

    pdf.savefig(fig)
    plt.close(fig)


def _row_top(gs, row_idx, fig):
    """Return the figure-coordinate y of the top of gridspec row *row_idx*."""
    renderer = fig.canvas.get_renderer()
    bb = gs[row_idx].get_position(fig)
    return bb.y1 + 0.012


# ── Page 2+: heatmaps ───────────────────────────────────────────────────────

def _build_heatmap_pages(pdf, name, filtered, pitch_tag, pitch_types):
    """
    Heatmap pages (portrait letter) — one row per pitch type,
    three columns: vs All Batters · vs RHB · vs LHB.
    Fits up to 3 pitch types per page.
    """
    ROWS_PER_PAGE = 3

    for page_start in range(0, len(pitch_types), ROWS_PER_PAGE):
        page_types = pitch_types[page_start:page_start + ROWS_PER_PAGE]
        n_rows = len(page_types)

        fig = plt.figure(figsize=(8.5, 11), facecolor="white")

        # Banner
        ax_b = fig.add_axes([0, 0.93, 1, 0.07])
        ax_b.set_facecolor(_NAVY)
        ax_b.set_xlim(0, 1)
        ax_b.set_ylim(0, 1)
        ax_b.text(0.5, 0.58, f"{name}  —  Pitching Heatmaps",
                  ha="center", va="center",
                  fontsize=15, fontweight="bold", color="white",
                  fontfamily="sans-serif")
        for sp in ax_b.spines.values():
            sp.set_visible(False)
        ax_b.set_xticks([])
        ax_b.set_yticks([])
        fig.add_artist(plt.Line2D(
            [0, 1], [0.93, 0.93],
            color=_RED, linewidth=2.5, transform=fig.transFigure, zorder=5,
        ))

        gs = fig.add_gridspec(
            nrows=n_rows, ncols=3, wspace=0.06, hspace=0.25,
            top=0.90, bottom=0.03, left=0.05, right=0.95,
        )

        for row_idx, ptype in enumerate(page_types):
            if pitch_tag in filtered.columns:
                pt_df = filtered[filtered[pitch_tag] == ptype]
            else:
                pt_df = filtered

            batter_filters = [
                (pt_df, f"{ptype} vs All Batters"),
                (
                    pt_df[pt_df["batter_side"] == "Right"]
                    if "batter_side" in pt_df.columns
                    else pd.DataFrame(),
                    f"{ptype} vs RHB",
                ),
                (
                    pt_df[pt_df["batter_side"] == "Left"]
                    if "batter_side" in pt_df.columns
                    else pd.DataFrame(),
                    f"{ptype} vs LHB",
                ),
            ]

            for col_idx, (sub_df, title) in enumerate(batter_filters):
                ax = fig.add_subplot(gs[row_idx, col_idx])
                plotly_fig = build_heatmap(sub_df)
                plotly_fig.update_layout(
                    title=dict(text=title, font=dict(size=10)),
                    margin=dict(l=5, r=5, t=30, b=5),
                )
                try:
                    img = _plotly_to_image(plotly_fig, width=300, height=280)
                    ax.imshow(img)
                except Exception:
                    ax.text(0.5, 0.5, "Chart unavailable",
                            ha="center", va="center", fontsize=7,
                            transform=ax.transAxes, color="gray")
                ax.axis("off")

        # Footer
        fig.text(0.5, 0.007,
                 "Generated by SLUGGER Pitching Widget",
                 ha="center", fontsize=5.5, color="#aaaaaa",
                 fontfamily="sans-serif", style="italic")

        pdf.savefig(fig)
        plt.close(fig)
