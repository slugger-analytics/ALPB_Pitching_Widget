"""
PDF report generation.

Generates pitcher scouting report PDFs using matplotlib for plots
and FPDF2 for PDF assembly.
Equivalent to getPDFReport.R and the .Rmd templates.
"""

import tempfile
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from python_app.analysis.pitch_split import get_pitch_type_percentages


# Pitch colors for matplotlib scatter plots (matches R version)
PITCH_COLORS = {
    "Fastball": "red",
    "Four-Seam": "red",
    "Changeup": "blue",
    "ChangeUp": "blue",
    "Sinker": "green",
    "Curveball": "brown",
    "Slider": "purple",
    "Splitter": "black",
    "Cutter": "pink",
    "Untagged": "gray",
}

AXIS_LABELS = {
    "induced_vert_break": "Induced Vertical Break (in)",
    "horz_break": "Horizontal Break (in)",
    "rel_speed": "Velocity (mph)",
}

AXIS_SHORT_LABELS = {
    "induced_vert_break": "Ind. Vert. Break",
    "horz_break": "Horz. Break",
    "rel_speed": "Velocity",
}


def _mpl_scatter(ax, df, x_axis, y_axis, tag):
    """Draw a scatter plot on a matplotlib Axes."""
    if df is None or df.empty:
        return

    plot_df = df.copy()
    if tag in plot_df.columns:
        plot_df["TagStatus"] = plot_df[tag].apply(
            lambda v: "Untagged" if pd.isna(v) or v == "Undefined" else str(v)
        )
    else:
        plot_df["TagStatus"] = "Untagged"

    for ptype in plot_df["TagStatus"].unique():
        subset = plot_df[plot_df["TagStatus"] == ptype]
        color = PITCH_COLORS.get(ptype, "gray")
        ax.scatter(
            pd.to_numeric(subset[x_axis], errors="coerce"),
            pd.to_numeric(subset[y_axis], errors="coerce"),
            c=color,
            label=ptype,
            alpha=0.7,
            s=15,
        )

    title = f"{AXIS_SHORT_LABELS.get(y_axis, y_axis)} vs. {AXIS_SHORT_LABELS.get(x_axis, x_axis)}"
    ax.set_title(title, fontsize=9)
    ax.set_xlabel(AXIS_LABELS.get(x_axis, x_axis), fontsize=7)
    ax.set_ylabel(AXIS_LABELS.get(y_axis, y_axis), fontsize=7)
    ax.tick_params(labelsize=6)


def _mpl_heatmap(ax, df, title=""):
    """Draw a heatmap on a matplotlib Axes."""
    # Strike zone
    sz = patches.Rectangle((-10 / 12, 1.5), 20 / 12, 2.0, linewidth=2, edgecolor="black", facecolor="none")

    if df is not None and not df.empty:
        plot_df = df[["plate_loc_side", "plate_loc_height"]].copy()
        plot_df["plate_loc_side"] = pd.to_numeric(plot_df["plate_loc_side"], errors="coerce")
        plot_df["plate_loc_height"] = pd.to_numeric(plot_df["plate_loc_height"], errors="coerce")
        plot_df = plot_df.dropna()
        plot_df = plot_df[np.isfinite(plot_df["plate_loc_side"]) & np.isfinite(plot_df["plate_loc_height"])]
    else:
        plot_df = pd.DataFrame()

    if not plot_df.empty and len(plot_df) >= 2:
        x = plot_df["plate_loc_side"].values
        y = plot_df["plate_loc_height"].values

        x_grid = np.linspace(-1.5, 1.5, 100)
        y_grid = np.linspace(0, 4, 100)
        xx, yy = np.meshgrid(x_grid, y_grid)

        try:
            kernel = gaussian_kde(np.vstack([x, y]), bw_method=1.0)
            z = kernel(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
            z[z < 0.001] = np.nan
            ax.pcolormesh(
                xx,
                yy,
                z,
                cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
                    "custom", ["white", "blue", "green", "yellow", "red"]
                ),
                shading="gouraud",
            )
        except np.linalg.LinAlgError:
            pass

    ax.add_patch(sz)
    ax.set_xlim(-16 / 12, 16 / 12)
    ax.set_ylim(1, 4)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    if title:
        ax.set_title(title, fontsize=8)


def _render_table(ax, df, title=""):
    """Render a pandas DataFrame as a matplotlib table."""
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=10, fontweight="bold", pad=10)
    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=10)
        return

    col_labels = list(df.columns)
    cell_text = df.values.tolist()

    table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(6)
    table.scale(1, 1.3)

    # Stripe rows
    for i, key in enumerate(table.get_celld()):
        cell = table[key]
        if key[0] == 0:
            cell.set_facecolor("#17a2b8")
            cell.set_text_props(color="white", fontweight="bold")
        elif key[0] % 2 == 0:
            cell.set_facecolor("#f2f2f2")


def generate_pdf(name, season_stats=None, pitch_data=None, pitch_tag="auto_pitch_type"):
    """
    Generate a pitcher scouting report PDF.

    Chooses content based on data availability (mirrors the 4 Rmd templates).

    Args:
        name: Pitcher name.
        season_stats: DataFrame of season stats, or None.
        pitch_data: DataFrame of pitch-by-pitch data, or None.
        pitch_tag: Pitch tagging column name.

    Returns:
        Path to the generated PDF file.
    """
    output_path = tempfile.mktemp(suffix=".pdf")

    has_stats = season_stats is not None and not season_stats.empty
    has_pitches = pitch_data is not None and not pitch_data.empty

    with PdfPages(output_path) as pdf:
        # --- Page 1: Title + stats + movement graphs ---
        fig = plt.figure(figsize=(11, 8.5))

        # Title
        fig.suptitle(f"{name} Pitching Report", fontsize=18, fontweight="bold", y=0.98)

        if not has_stats and not has_pitches:
            ax = fig.add_subplot(111)
            ax.axis("off")
            ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=16)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            return output_path

        row_count = 0
        if has_stats:
            row_count += 1
        if has_pitches:
            row_count += 2  # movement graphs + pitch split

        grid_rows = max(row_count, 1)
        gs = fig.add_gridspec(grid_rows, 1, hspace=0.5, top=0.92, bottom=0.05, left=0.05, right=0.95)

        current_row = 0

        # Season stats table
        if has_stats:
            ax_stats = fig.add_subplot(gs[current_row])
            _render_table(ax_stats, season_stats, title="Season Stats Overview")
            current_row += 1

        # Movement graphs (3 side by side)
        if has_pitches:
            inner_gs = gs[current_row].subgridspec(1, 3, wspace=0.3)
            axes = [fig.add_subplot(inner_gs[0, i]) for i in range(3)]

            _mpl_scatter(axes[0], pitch_data, "horz_break", "induced_vert_break", pitch_tag)
            _mpl_scatter(axes[1], pitch_data, "rel_speed", "induced_vert_break", pitch_tag)
            _mpl_scatter(axes[2], pitch_data, "rel_speed", "horz_break", pitch_tag)

            # Add shared legend below the movement graphs
            handles, labels = axes[0].get_legend_handles_labels()
            if handles:
                fig.legend(handles, labels, loc="lower center", ncol=len(labels), fontsize=6)

            current_row += 1

        # Pitch split table
        if has_pitches:
            filtered = pitch_data.copy()
            if pitch_tag in filtered.columns:
                filtered = filtered.dropna(subset=[pitch_tag])
                filtered = filtered[filtered[pitch_tag] != "Undefined"]
            split_df = get_pitch_type_percentages(filtered, pitch_tag)
            ax_split = fig.add_subplot(gs[current_row])
            _render_table(ax_split, split_df, title="Pitch Usage by Count")

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # --- Heatmap pages (one per pitch type) ---
        if has_pitches:
            filtered = pitch_data.copy()
            if pitch_tag in filtered.columns:
                filtered = filtered.dropna(subset=[pitch_tag])
                filtered = filtered[filtered[pitch_tag] != "Undefined"]

            pitch_types = filtered[pitch_tag].unique()

            for ptype in pitch_types:
                type_df = filtered[filtered[pitch_tag] == ptype]

                fig_h, axes_h = plt.subplots(1, 3, figsize=(11, 4))
                fig_h.suptitle(f"Pitch Location Heatmaps", fontsize=12, fontweight="bold")

                _mpl_heatmap(axes_h[0], type_df, f"{ptype} vs All Batters")

                right_df = type_df[type_df["batter_side"] == "Right"] if "batter_side" in type_df.columns else pd.DataFrame()
                _mpl_heatmap(axes_h[1], right_df, f"{ptype} vs RHB")

                left_df = type_df[type_df["batter_side"] == "Left"] if "batter_side" in type_df.columns else pd.DataFrame()
                _mpl_heatmap(axes_h[2], left_df, f"{ptype} vs LHB")

                pdf.savefig(fig_h, bbox_inches="tight")
                plt.close(fig_h)

    return output_path
