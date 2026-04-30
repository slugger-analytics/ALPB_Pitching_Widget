#!/usr/bin/env python3
"""Generate sample-review artifacts without private API access."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DATA_SOURCE"] = "sample"

from python_app.features.heatmaps import build_heatmap
from python_app.features.pitch_split import compute_pitch_split
from python_app.features.scatter_plots import build_scatter
from python_app.lib.cache import DataCache


def main() -> int:
    output_dir = ROOT / "output" / "sample_review"
    output_dir.mkdir(parents=True, exist_ok=True)

    cache = DataCache()
    cache.load_roster()

    player = cache.pitchers_df.iloc[0]
    playerlinkid = str(player["playerlinkid"]).strip()
    full_name = str(player["full_name"]).strip()

    stats = cache.get_season_stats(playerlinkid)
    alpb_id = cache.get_alpb_id(playerlinkid)
    pitch_df = pd.DataFrame(cache.get_pitch_data(alpb_id))
    split_df = compute_pitch_split(pitch_df, "auto_pitch_type")

    vel_fig = build_scatter(
        pitch_df,
        "rel_speed",
        "induced_vert_break",
        "auto_pitch_type",
    )
    break_fig = build_scatter(
        pitch_df,
        "horz_break",
        "induced_vert_break",
        "auto_pitch_type",
    )
    rh_fig = build_heatmap(pitch_df[pitch_df["batter_side"] == "Right"])
    lh_fig = build_heatmap(pitch_df[pitch_df["batter_side"] == "Left"])

    slug = full_name.lower().replace(" ", "_")
    if stats is not None:
        stats.to_csv(output_dir / f"{slug}_season_stats.csv", index=False)
    split_df.to_csv(output_dir / f"{slug}_pitch_split.csv", index=False)
    pitch_df.to_csv(output_dir / f"{slug}_pitch_data.csv", index=False)
    vel_fig.write_html(output_dir / f"{slug}_velocity_scatter.html")
    break_fig.write_html(output_dir / f"{slug}_break_scatter.html")
    rh_fig.write_html(output_dir / f"{slug}_heatmap_rhb.html")
    lh_fig.write_html(output_dir / f"{slug}_heatmap_lhb.html")

    summary = output_dir / "README.txt"
    summary.write_text(
        "\n".join(
            [
                "Sample review artifacts generated successfully.",
                f"Pitcher: {full_name}",
                f"Output directory: {output_dir}",
                "Files include representative CSV summaries and HTML visualizations.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote sample artifacts to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
