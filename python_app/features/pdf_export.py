"""
PDF scouting report export — single-page portrait letter (8.5 × 11 in).

Callback: triggered by the Download PDF button.
Generation: converts Plotly figures from the feature modules into images,
then composes everything onto ONE page with matplotlib.

Uses the same public methods that power the Dash UI:
  - scatter_plots.build_scatter()      → pitch movement charts
  - heatmaps.build_heatmap()           → strike-zone density maps
  - pitch_split.compute_pitch_split()  → count-based usage table
"""

import io
import tempfile
import traceback
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
_NAVY  = TABLE_HEADER_COLOR   # "#002D72"
_RED   = "#C8102E"
_LGRAY = "#f5f6fa"
_MGRAY = "#dcdde1"

# ── Check kaleido availability at import time ────────────────────────────────
_KALEIDO_OK = False
try:
    import kaleido  # noqa: F401
    _KALEIDO_OK = True
except ImportError:
    print(
        "\n⚠  kaleido is not installed — PDF charts will show placeholder text.\n"
        "   Fix:  pip install 'kaleido>=0.2.1,<1.0'\n"
    )


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
    """Convert a Plotly figure to a numpy image array for matplotlib.

    Returns None if kaleido is unavailable or the conversion fails.
    """
    if not _KALEIDO_OK:
        return None
    try:
        img_bytes = fig.to_image(format="png", width=width, height=height, scale=scale)
        return plt.imread(io.BytesIO(img_bytes))
    except Exception:
        traceback.print_exc()
        return None


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
    """Thin dark-navy banner at the top of the page."""
    ax = fig.add_axes([0, 0.945, 1, 0.055])
    ax.set_facecolor(_NAVY)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0.5, 0.60, f"{name}  —  Pitching Report",
            ha="center", va="center",
            fontsize=15, fontweight="bold", color="white",
            fontfamily="sans-serif")
    ax.text(0.5, 0.15, date.today().strftime("%B %d, %Y"),
            ha="center", va="center",
            fontsize=7, color="#8eafd4", fontfamily="sans-serif")
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    fig.add_artist(plt.Line2D(
        [0, 1], [0.945, 0.945],
        color=_RED, linewidth=2, transform=fig.transFigure, zorder=5,
    ))


def _section_label(fig, y, text):
    """Small section heading at figure-y coordinate."""
    fig.text(0.06, y, text,
             fontsize=7.5, fontweight="bold", color=_NAVY,
             fontfamily="sans-serif")
    fig.add_artist(plt.Line2D(
        [0.05, 0.95], [y - 0.004, y - 0.004],
        color=_MGRAY, linewidth=0.6, transform=fig.transFigure,
    ))


def _render_table(ax, df):
    """Render a DataFrame as a compact styled table."""
    ax.axis("off")
    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data available",
                ha="center", va="center", fontsize=7, color="gray")
        return

    display = df.copy()
    for c in display.columns:
        display[c] = display[c].astype(str).str[:18]

    tbl = ax.table(
        cellText=display.values.tolist(),
        colLabels=list(display.columns),
        loc="center", cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(4.5)
    tbl.scale(1, 0.95)
    tbl.auto_set_column_width(list(range(len(display.columns))))

    for (r, c), cell in tbl.get_celld().items():
        cell.set_linewidth(0.2)
        cell.set_edgecolor(_MGRAY)
        if r == 0:
            cell.set_facecolor(_NAVY)
            cell.set_text_props(color="white", fontweight="bold", fontsize=5)
        elif r % 2 == 0:
            cell.set_facecolor(_LGRAY)
        else:
            cell.set_facecolor("white")


def _embed_plotly(ax, plotly_fig, w=300, h=230):
    """Convert a Plotly figure and show it on *ax*. Graceful fallback."""
    ax.axis("off")
    if plotly_fig is None or not plotly_fig.data:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                fontsize=6, color="gray", transform=ax.transAxes)
        return
    img = _plotly_to_image(plotly_fig, width=w, height=h)
    if img is not None:
        ax.imshow(img)
    else:
        ax.text(0.5, 0.5,
                "Install kaleido to\nenable chart export",
                ha="center", va="center", fontsize=6, color="gray",
                transform=ax.transAxes)


# ── PDF generation ───────────────────────────────────────────────────────────

def _generate_pdf(name, player, season_stats, pitch_data, pitch_tag):
    """Build a single-page scouting report PDF and return the file path."""
    output_path = tempfile.mktemp(suffix=".pdf")
    has_stats = season_stats is not None and not season_stats.empty
    has_pitches = pitch_data is not None and not pitch_data.empty

    filtered = None
    split_df = None
    if has_pitches:
        filtered = pitch_data.copy()
        if pitch_tag in filtered.columns:
            filtered = filtered.dropna(subset=[pitch_tag])
            filtered = filtered[filtered[pitch_tag] != "Undefined"]
        split_df = compute_pitch_split(filtered, pitch_tag)

    photo = _download_photo(player.get("photo", ""))

    # --- Pre-render all Plotly images BEFORE building the PDF figure ------
    scatter_images = []
    if has_pitches and filtered is not None and not filtered.empty:
        for x_col, y_col in [
            ("horz_break", "induced_vert_break"),
            ("rel_speed",  "induced_vert_break"),
            ("rel_speed",  "horz_break"),
        ]:
            pfig = build_scatter(filtered, x_col, y_col, pitch_tag)
            pfig.update_layout(margin=dict(l=40, r=10, t=28, b=40))
            scatter_images.append(_plotly_to_image(pfig, width=290, height=220))

    # --- Build PDF --------------------------------------------------------
    with PdfPages(output_path) as pdf:
        _build_page(
            pdf, name, player, photo,
            has_stats, season_stats,
            has_pitches, split_df,
            scatter_images,
        )

    return output_path


def _build_page(
    pdf, name, player, photo,
    has_stats, season_stats,
    has_pitches, split_df,
    scatter_images,
):
    """
    ONE portrait letter page (8.5 × 11 in), top-to-bottom:

      Banner
      ── PITCHER INFORMATION ──
      [Photo]  Bio text
      ── SEASON STATS ──
      Stats table
      ── PITCH MOVEMENT ──
      [Scatter 1] [Scatter 2] [Scatter 3]
      ── PITCH USAGE BY COUNT ──
      Split table
      Footer
    """
    fig = plt.figure(figsize=(8.5, 11), facecolor="white")
    _draw_banner(fig, name)

    # 4-row grid — very tight
    gs = fig.add_gridspec(
        nrows=4, ncols=1,
        height_ratios=[1.1, 0.7, 1.8, 1.6],
        hspace=0.08,
        top=0.925, bottom=0.02, left=0.05, right=0.95,
    )

    # ── Row 0 — Photo + bio ──────────────────────────────────────────────
    _section_label(fig, 0.935, "PITCHER INFORMATION")

    row0 = gs[0].subgridspec(1, 2, wspace=0.06, width_ratios=[1, 3.5])

    # Photo — small, left
    ax_photo = fig.add_subplot(row0[0, 0])
    ax_photo.axis("off")
    if photo is not None:
        ax_photo.imshow(photo, aspect="auto")
        for sp in ax_photo.spines.values():
            sp.set_visible(True); sp.set_color(_MGRAY); sp.set_linewidth(0.8)
    else:
        ax_photo.set_facecolor(_LGRAY)
        ax_photo.text(0.5, 0.5, "No photo", ha="center", va="center",
                      fontsize=7, color="gray", transform=ax_photo.transAxes)

    # Bio — right of photo, compact key-value pairs
    ax_bio = fig.add_subplot(row0[0, 1])
    ax_bio.axis("off")
    fields = [
        ("Name",   player.get("full_name", "")),
        ("Team",   player.get("teamname", "")),
        ("Throws", player.get("throws", "")),
        ("Bats",   player.get("bats", "")),
        ("Ht/Wt", f"{player.get('height', '')} / {player.get('weight', '')}"),
        ("From",   player.get("hometown", "")),
    ]
    y = 0.90
    for label, val in fields:
        if not val or val.strip() == "/":
            continue
        ax_bio.text(0.01, y, f"{label}:", transform=ax_bio.transAxes,
                    fontsize=6.5, fontweight="bold", color=_NAVY,
                    fontfamily="sans-serif", va="top")
        ax_bio.text(0.12, y, str(val), transform=ax_bio.transAxes,
                    fontsize=6.5, color="#333", fontfamily="sans-serif", va="top")
        y -= 0.16

    # ── Row 1 — Season stats table ───────────────────────────────────────
    bb1 = gs[1].get_position(fig)
    _section_label(fig, bb1.y1 + 0.008, "SEASON STATS")

    ax_stats = fig.add_subplot(gs[1])
    _render_table(ax_stats, season_stats)

    # ── Row 2 — Scatter plots ────────────────────────────────────────────
    bb2 = gs[2].get_position(fig)
    _section_label(fig, bb2.y1 + 0.008, "PITCH MOVEMENT")

    scatter_gs = gs[2].subgridspec(1, 3, wspace=0.02)
    for j in range(3):
        ax = fig.add_subplot(scatter_gs[0, j])
        ax.axis("off")
        if j < len(scatter_images) and scatter_images[j] is not None:
            ax.imshow(scatter_images[j])
        elif has_pitches:
            ax.text(0.5, 0.5,
                    "Install kaleido to\nenable chart export",
                    ha="center", va="center", fontsize=6, color="gray",
                    transform=ax.transAxes)
        else:
            ax.text(0.5, 0.5, "No pitch data", ha="center", va="center",
                    fontsize=6, color="gray", transform=ax.transAxes)

    # ── Row 3 — Pitch split table ────────────────────────────────────────
    bb3 = gs[3].get_position(fig)
    _section_label(fig, bb3.y1 + 0.008, "PITCH USAGE BY COUNT")

    ax_split = fig.add_subplot(gs[3])
    _render_table(ax_split, split_df)

    # ── Footer ───────────────────────────────────────────────────────────
    fig.text(0.5, 0.005,
             "Generated by SLUGGER Pitching Widget",
             ha="center", fontsize=5, color="#aaa",
             fontfamily="sans-serif", style="italic")

    pdf.savefig(fig)
    plt.close(fig)
