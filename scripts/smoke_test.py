#!/usr/bin/env python3
"""Minimal smoke tests for both sample and live dashboard data sources."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-source",
        choices=["sample", "live"],
        default=os.getenv("DATA_SOURCE", "sample"),
        help="Choose sample files or the private live APIs.",
    )
    args = parser.parse_args()

    os.environ["DATA_SOURCE"] = args.data_source

    import pandas as pd

    from python_app.features.heatmaps import build_heatmap
    from python_app.features.pitch_split import compute_pitch_split
    from python_app.features.scatter_plots import build_scatter
    from python_app.lib.cache import DataCache

    cache = DataCache()
    cache.load_roster()
    if cache.pitchers_df.empty:
        raise RuntimeError("Roster load failed: no pitchers were returned.")

    player = cache.pitchers_df.iloc[0]
    playerlinkid = str(player["playerlinkid"]).strip()
    full_name = str(player["full_name"]).strip()

    stats = cache.get_season_stats(playerlinkid)
    if stats is None or stats.empty:
        raise RuntimeError(f"No season stats returned for {full_name}.")

    alpb_id = cache.get_alpb_id(playerlinkid)
    if not alpb_id:
        raise RuntimeError(f"No ALPB player ID returned for {full_name}.")

    pitch_records = cache.get_pitch_data(alpb_id)
    if not pitch_records:
        raise RuntimeError(f"No pitch data returned for {full_name}.")

    pitch_df = pd.DataFrame(pitch_records)
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
    split_df = compute_pitch_split(pitch_df, "auto_pitch_type")
    heatmap_fig = build_heatmap(pitch_df[pitch_df["batter_side"] == "Right"])

    if not vel_fig.data:
        raise RuntimeError("Velocity scatter plot did not render any traces.")
    if not break_fig.data:
        raise RuntimeError("Break scatter plot did not render any traces.")
    if split_df.empty:
        raise RuntimeError("Pitch split table was empty.")
    if not heatmap_fig.data:
        raise RuntimeError("Heatmap figure did not render any traces.")

    summary = {
        "data_source": args.data_source,
        "pitcher_count": int(len(cache.pitchers_df)),
        "example_player": full_name,
        "example_team": str(player.get("teamname", "")).strip(),
        "season_stat_rows": int(len(stats)),
        "pitch_rows": int(len(pitch_df)),
        "pitch_types": sorted(
            str(value)
            for value in pitch_df["auto_pitch_type"].dropna().astype(str).unique().tolist()
        ),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
