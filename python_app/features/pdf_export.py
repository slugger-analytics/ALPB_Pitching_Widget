"""
PDF scouting report export.

Callback: triggered by the Download PDF button.
Generation: builds a single-page matplotlib report and sends it.
"""

import tempfile
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from dash import dcc, callback, Input, Output, State, no_update

from python_app.config import PITCH_COLORS, AXIS_LABELS, AXIS_SHORT_LABELS, TABLE_HEADER_COLOR
from python_app.lib.cache import cache
from python_app.features.pitch_split import compute_pitch_split


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

    pdf_path = _generate_pdf(selected_name, stats, pitch_df, tag)
    return dcc.send_file(pdf_path, filename=f"{selected_name} Pitcher Report.pdf")


# ── PDF generation ───────────────────────────────────────────────────────────

def _generate_pdf(name, season_stats, pitch_data, pitch_tag):
    """Build a single-page scouting report and return the file path."""
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

    with PdfPages(output_path) as pdf:
        fig = plt.figure(figsize=(11, 8.5))

        # Determine which sections to include
        sections, heights = [], []
        if has_stats:
            sections.append("stats"); heights.append(1.0)
        if has_pitches:
            sections.append("graphs"); heights.append(2.5)
        if has_pitches and split_df is not None and not split_df.empty:
            sections.append("split"); heights.append(1.2)
        if has_pitches:
            sections.append("heat"); heights.append(2.5)

        if not sections:
            ax = fig.add_subplot(111); ax.axis("off")
            fig.suptitle(f"{name} Pitching Report", fontsize=16, fontweight="bold", y=0.95)
            ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=14)
            pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)
            return output_path

        fig.suptitle(f"{name} Pitching Report", fontsize=14, fontweight="bold", y=0.97)
        fig.text(0.5, 0.945, date.today().strftime("%B %d, %Y"), ha="center", fontsize=7, color="gray")

        gs = fig.add_gridspec(
            nrows=len(sections), ncols=1, height_ratios=heights,
            hspace=0.45, top=0.92, bottom=0.03, left=0.04, right=0.96,
        )

        for i, sec in enumerate(sections):
            if sec == "stats":
                _table(fig.add_subplot(gs[i]), season_stats, "Season Stats")

            elif sec == "graphs":
                inner = gs[i].subgridspec(1, 4, wspace=0.35, width_ratios=[1, 1, 1, 0.3])
                axes = [fig.add_subplot(inner[0, j]) for j in range(3)]
                ax_leg = fig.add_subplot(inner[0, 3])
                _scatter(axes[0], filtered, "horz_break", "induced_vert_break", pitch_tag)
                _scatter(axes[1], filtered, "rel_speed", "induced_vert_break", pitch_tag)
                _scatter(axes[2], filtered, "rel_speed", "horz_break", pitch_tag)
                ax_leg.axis("off")
                h, l = axes[0].get_legend_handles_labels()
                if h:
                    ax_leg.legend(h, l, loc="center", fontsize=6, frameon=True,
                                  title="Pitch Type", title_fontsize=6.5)

            elif sec == "split":
                _table(fig.add_subplot(gs[i]), split_df, "Pitch Usage by Count (%)")

            elif sec == "heat":
                inner = gs[i].subgridspec(1, 3, wspace=0.15)
                _heatmap(fig.add_subplot(inner[0, 0]), filtered, "All Pitches vs All Batters")
                r = filtered[filtered["batter_side"] == "Right"] if "batter_side" in filtered.columns else pd.DataFrame()
                l = filtered[filtered["batter_side"] == "Left"]  if "batter_side" in filtered.columns else pd.DataFrame()
                _heatmap(fig.add_subplot(inner[0, 1]), r, "All Pitches vs RHB")
                _heatmap(fig.add_subplot(inner[0, 2]), l, "All Pitches vs LHB")

        pdf.savefig(fig); plt.close(fig)
    return output_path


# ── Matplotlib drawing helpers (private) ─────────────────────────────────────

def _scatter(ax, df, x_col, y_col, tag):
    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=7, transform=ax.transAxes)
        return
    tmp = df.copy()
    tmp["_t"] = tmp[tag].apply(lambda v: "Untagged" if pd.isna(v) or v == "Undefined" else str(v)) if tag in tmp.columns else "Untagged"
    for pt in sorted(tmp["_t"].unique()):
        sub = tmp[tmp["_t"] == pt]
        ax.scatter(pd.to_numeric(sub[x_col], errors="coerce"),
                   pd.to_numeric(sub[y_col], errors="coerce"),
                   c=PITCH_COLORS.get(pt, "gray"), label=pt, alpha=0.7, s=8, edgecolors="none")
    ax.set_title(f"{AXIS_SHORT_LABELS.get(y_col, y_col)} vs. {AXIS_SHORT_LABELS.get(x_col, x_col)}", fontsize=7, pad=3)
    ax.set_xlabel(AXIS_LABELS.get(x_col, x_col), fontsize=5.5)
    ax.set_ylabel(AXIS_LABELS.get(y_col, y_col), fontsize=5.5)
    ax.tick_params(labelsize=5, length=2, pad=1)


def _heatmap(ax, df, title=""):
    sz = patches.Rectangle((-10/12, 1.5), 20/12, 2.0, lw=1.5, ec="black", fc="none", zorder=5)
    if df is not None and not df.empty:
        loc = df[["plate_loc_side", "plate_loc_height"]].copy()
        loc["plate_loc_side"] = pd.to_numeric(loc["plate_loc_side"], errors="coerce")
        loc["plate_loc_height"] = pd.to_numeric(loc["plate_loc_height"], errors="coerce")
        loc = loc.dropna()
        loc = loc[np.isfinite(loc["plate_loc_side"]) & np.isfinite(loc["plate_loc_height"])]
    else:
        loc = pd.DataFrame()
    if not loc.empty and len(loc) >= 2:
        x, y = loc["plate_loc_side"].values, loc["plate_loc_height"].values
        xg, yg = np.linspace(-1.5, 1.5, 100), np.linspace(0, 4, 100)
        xx, yy = np.meshgrid(xg, yg)
        try:
            k = gaussian_kde(np.vstack([x, y]), bw_method=1.0)
            z = k(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
            z[z < 0.001] = np.nan
            cmap = matplotlib.colors.LinearSegmentedColormap.from_list("c", ["white","blue","green","yellow","red"])
            ax.pcolormesh(xx, yy, z, cmap=cmap, shading="gouraud")
        except np.linalg.LinAlgError:
            pass
    ax.add_patch(sz)
    ax.set_xlim(-16/12, 16/12); ax.set_ylim(1, 4)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    if title:
        ax.set_title(title, fontsize=6.5, pad=2)


def _table(ax, df, title=""):
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=8, fontweight="bold", loc="left", pad=2)
    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=8)
        return
    tbl = ax.table(cellText=df.values.tolist(), colLabels=list(df.columns), loc="center", cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(5); tbl.scale(1, 1.1)
    for key in tbl.get_celld():
        cell = tbl[key]; cell.set_linewidth(0.3)
        if key[0] == 0:
            cell.set_facecolor(TABLE_HEADER_COLOR); cell.set_text_props(color="white", fontweight="bold")
        elif key[0] % 2 == 0:
            cell.set_facecolor("#f2f2f2")
