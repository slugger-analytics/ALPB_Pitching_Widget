"""
PDF report generation.

Generates a single-page pitcher scouting report PDF using matplotlib.
Equivalent to getPDFReport.R and the .Rmd templates.
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
    "induced_vert_break": "Ind. Vert. Break (in)",
    "horz_break": "Horz. Break (in)",
    "rel_speed": "Velocity (mph)",
}

AXIS_SHORT_LABELS = {
    "induced_vert_break": "Ind. Vert. Break",
    "horz_break": "Horz. Break",
    "rel_speed": "Velocity",
}


def _mpl_scatter(ax, df, x_axis, y_axis, tag):
    """Draw a compact scatter plot on a matplotlib Axes."""
    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=7, transform=ax.transAxes)
        return

    plot_df = df.copy()
    if tag in plot_df.columns:
        plot_df["TagStatus"] = plot_df[tag].apply(
            lambda v: "Untagged" if pd.isna(v) or v == "Undefined" else str(v)
        )
    else:
        plot_df["TagStatus"] = "Untagged"

    for ptype in sorted(plot_df["TagStatus"].unique()):
        subset = plot_df[plot_df["TagStatus"] == ptype]
        color = PITCH_COLORS.get(ptype, "gray")
        ax.scatter(
            pd.to_numeric(subset[x_axis], errors="coerce"),
            pd.to_numeric(subset[y_axis], errors="coerce"),
            c=color,
            label=ptype,
            alpha=0.7,
            s=8,
            edgecolors="none",
        )

    title = f"{AXIS_SHORT_LABELS.get(y_axis, y_axis)} vs. {AXIS_SHORT_LABELS.get(x_axis, x_axis)}"
    ax.set_title(title, fontsize=7, pad=3)
    ax.set_xlabel(AXIS_LABELS.get(x_axis, x_axis), fontsize=5.5)
    ax.set_ylabel(AXIS_LABELS.get(y_axis, y_axis), fontsize=5.5)
    ax.tick_params(labelsize=5, length=2, pad=1)


def _mpl_heatmap(ax, df, title=""):
    """Draw a compact heatmap on a matplotlib Axes."""
    sz = patches.Rectangle((-10 / 12, 1.5), 20 / 12, 2.0,
                           linewidth=1.5, edgecolor="black", facecolor="none", zorder=5)

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
                xx, yy, z,
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
        ax.set_title(title, fontsize=6.5, pad=2)


def _render_table(ax, df, title=""):
    """Render a compact pandas DataFrame as a matplotlib table."""
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=8, fontweight="bold", loc="left", pad=2)
    if df is None or df.empty:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=8)
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
    table.set_fontsize(5)
    table.scale(1, 1.1)

    for key in table.get_celld():
        cell = table[key]
        cell.set_linewidth(0.3)
        if key[0] == 0:
            cell.set_facecolor("#17a2b8")
            cell.set_text_props(color="white", fontweight="bold")
        elif key[0] % 2 == 0:
            cell.set_facecolor("#f2f2f2")


def generate_pdf(name, season_stats=None, pitch_data=None, pitch_tag="auto_pitch_type"):
    """
    Generate a single-page pitcher scouting report PDF.

    Layout (landscape 11x8.5):
      - Title header
      - Season stats table
      - 3 movement scatter plots side by side
      - Pitch usage by count table
      - 3 heatmaps (All pitches: vs All Batters / vs RHB / vs LHB)

    Adapts content based on data availability.

    Returns:
        Path to the generated PDF file.
    """
    output_path = tempfile.mktemp(suffix=".pdf")

    has_stats = season_stats is not None and not season_stats.empty
    has_pitches = pitch_data is not None and not pitch_data.empty

    # Prepare filtered pitch data once
    filtered_pitches = None
    split_df = None
    if has_pitches:
        filtered_pitches = pitch_data.copy()
        if pitch_tag in filtered_pitches.columns:
            filtered_pitches = filtered_pitches.dropna(subset=[pitch_tag])
            filtered_pitches = filtered_pitches[filtered_pitches[pitch_tag] != "Undefined"]
        split_df = get_pitch_type_percentages(filtered_pitches, pitch_tag)

    with PdfPages(output_path) as pdf:
        # Single landscape page
        fig = plt.figure(figsize=(11, 8.5))

        # --- Determine grid layout based on available data ---
        # Possible sections: stats, graphs, pitch_split, heatmaps
        sections = []
        # Height ratios: smaller for tables, larger for plots
        heights = []

        if has_stats:
            sections.append("stats")
            heights.append(1.0)

        if has_pitches:
            sections.append("graphs")
            heights.append(2.5)

        if has_pitches and split_df is not None and not split_df.empty:
            sections.append("pitch_split")
            heights.append(1.2)

        if has_pitches:
            sections.append("heatmaps")
            heights.append(2.5)

        if not sections:
            # No data at all
            ax = fig.add_subplot(111)
            ax.axis("off")
            fig.suptitle(f"{name} Pitching Report", fontsize=16, fontweight="bold", y=0.95)
            ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=14)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            return output_path

        # Title
        fig.suptitle(f"{name} Pitching Report", fontsize=14, fontweight="bold", y=0.97)
        fig.text(0.5, 0.945, date.today().strftime("%B %d, %Y"),
                 ha="center", fontsize=7, color="gray")

        gs = fig.add_gridspec(
            nrows=len(sections), ncols=1,
            height_ratios=heights,
            hspace=0.45,
            top=0.92, bottom=0.03, left=0.04, right=0.96,
        )

        for i, section in enumerate(sections):
            if section == "stats":
                ax_stats = fig.add_subplot(gs[i])
                _render_table(ax_stats, season_stats, title="Season Stats")

            elif section == "graphs":
                inner = gs[i].subgridspec(1, 4, wspace=0.35, width_ratios=[1, 1, 1, 0.3])
                ax0 = fig.add_subplot(inner[0, 0])
                ax1 = fig.add_subplot(inner[0, 1])
                ax2 = fig.add_subplot(inner[0, 2])
                ax_leg = fig.add_subplot(inner[0, 3])

                _mpl_scatter(ax0, filtered_pitches, "horz_break", "induced_vert_break", pitch_tag)
                _mpl_scatter(ax1, filtered_pitches, "rel_speed", "induced_vert_break", pitch_tag)
                _mpl_scatter(ax2, filtered_pitches, "rel_speed", "horz_break", pitch_tag)

                # Shared legend in the 4th slot
                ax_leg.axis("off")
                handles, labels = ax0.get_legend_handles_labels()
                if handles:
                    ax_leg.legend(handles, labels, loc="center", fontsize=6,
                                  frameon=True, title="Pitch Type", title_fontsize=6.5)

            elif section == "pitch_split":
                ax_split = fig.add_subplot(gs[i])
                _render_table(ax_split, split_df, title="Pitch Usage by Count (%)")

            elif section == "heatmaps":
                inner = gs[i].subgridspec(1, 3, wspace=0.15)
                ax_all = fig.add_subplot(inner[0, 0])
                ax_rhb = fig.add_subplot(inner[0, 1])
                ax_lhb = fig.add_subplot(inner[0, 2])

                _mpl_heatmap(ax_all, filtered_pitches, "All Pitches vs All Batters")

                if "batter_side" in filtered_pitches.columns:
                    right_df = filtered_pitches[filtered_pitches["batter_side"] == "Right"]
                    left_df = filtered_pitches[filtered_pitches["batter_side"] == "Left"]
                else:
                    right_df = pd.DataFrame()
                    left_df = pd.DataFrame()

                _mpl_heatmap(ax_rhb, right_df, "All Pitches vs RHB")
                _mpl_heatmap(ax_lhb, left_df, "All Pitches vs LHB")

        pdf.savefig(fig)
        plt.close(fig)

    return output_path
