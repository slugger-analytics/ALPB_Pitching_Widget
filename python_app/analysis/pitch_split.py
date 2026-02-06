"""
Pitch usage analysis.

Calculates pitch type percentages for each ball-strike count.
Equivalent to pitchSplit.R.
"""

import pandas as pd


def get_pitch_type_percentages(pitch_data, tag):
    """
    Calculate the percentage of each pitch type thrown in every ball-strike count.

    Args:
        pitch_data: DataFrame with pitch data including 'balls', 'strikes', and the tag column.
        tag: Column name for pitch classification ('auto_pitch_type' or 'tagged_pitch_type').

    Returns:
        DataFrame with 'Count' column and one column per pitch type containing percentages.
    """
    if pitch_data is None or pitch_data.empty:
        return pd.DataFrame(columns=["Count"])

    df = pitch_data.copy()

    # Filter out rows with missing count info or undefined pitch types
    df = df.dropna(subset=["balls", "strikes", tag])
    df = df[df[tag] != "Undefined"]

    if df.empty:
        return pd.DataFrame(columns=["Count"])

    # Create Count column in "B - S" format
    df["Count"] = df["balls"].astype(str) + " - " + df["strikes"].astype(str)

    # Count pitches per count per pitch type
    grouped = df.groupby(["Count", tag]).size().reset_index(name="pitch_count")

    # Calculate totals per count
    totals = grouped.groupby("Count")["pitch_count"].transform("sum")

    # Calculate percentages
    grouped["pct"] = (grouped["pitch_count"] / totals * 100).round(1)

    # Pivot to wide format: one column per pitch type
    result = grouped.pivot_table(
        index="Count", columns=tag, values="pct", fill_value=0
    ).reset_index()

    # Sort by count
    result = result.sort_values("Count").reset_index(drop=True)

    # Flatten column names
    result.columns.name = None

    return result
