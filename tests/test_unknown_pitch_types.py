"""The feed spells "unknown pitch type" in more than one way.

``auto_pitch_type`` carries real nulls AND the literal string ``"NaN"``.
``dropna()`` removes only the first, and the string then survives an
``!= "Undefined"`` test, so a pitch type named "NaN" was printed with real usage
percentages into the PITCH USAGE BY COUNT table of scouting reports — measured
on 10 of the 16 pages of a live Charleston team PDF (Lance Lusk: 12 such
pitches, Keyvius Sampson: 15, Miguel Pena: 17) — and appeared as a grey series
in the movement legend.

Four call sites spelled this filter out separately and had already drifted; they
now share one helper.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from python_app.lib.filters import (
    drop_unknown_pitch_types,
    is_known_pitch_type,
    known_pitch_types,
)

TAG = "auto_pitch_type"


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        TAG: ["Four-Seam", "NaN", "Slider", None, "Undefined", np.nan, "nan", "Cutter"],
        "rel_speed": [92, 88, 84, 90, 91, 89, 87, 90],
    })


def test_the_literal_string_nan_is_not_a_pitch_type():
    assert not is_known_pitch_type("NaN")
    assert not is_known_pitch_type("nan")
    assert not is_known_pitch_type("Undefined")
    assert not is_known_pitch_type(None)
    assert not is_known_pitch_type(np.nan)
    assert not is_known_pitch_type("")
    assert not is_known_pitch_type("   ")


def test_real_pitch_types_survive():
    for name in ("Four-Seam", "Slider", "Cutter", "Curveball", "Splitter"):
        assert is_known_pitch_type(name)


def test_dropping_unknowns_keeps_only_real_pitches():
    kept = drop_unknown_pitch_types(_frame(), TAG)
    assert sorted(kept[TAG]) == ["Cutter", "Four-Seam", "Slider"]


def test_the_dropdown_offers_no_placeholder_types():
    assert known_pitch_types(_frame(), TAG) == ["Cutter", "Four-Seam", "Slider"]


def test_a_missing_tag_column_is_passed_through_untouched():
    df = pd.DataFrame({"rel_speed": [90, 91]})
    assert len(drop_unknown_pitch_types(df, TAG)) == 2
    assert known_pitch_types(df, TAG) == []


def test_none_and_empty_frames_are_safe():
    assert drop_unknown_pitch_types(None, TAG) is None
    empty = pd.DataFrame({TAG: []})
    assert drop_unknown_pitch_types(empty, TAG).empty


def test_every_pitch_type_filter_uses_the_shared_helper():
    """A fifth copy of this filter would drift like the first four did."""
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "python_app"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "filters.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "Undefined":
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "compare pitch types through python_app.lib.filters instead: "
        + ", ".join(offenders)
    )
