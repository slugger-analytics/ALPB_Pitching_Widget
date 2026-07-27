"""Tests for the heatmap card titles.

The web card headers and the PDF section titles must both read
"Heat Map vs. RH/LH Batters" (note the period after "vs") and stay in sync.
"""

from __future__ import annotations

from typing import Iterator

RH_TITLE = "Heat Map vs. RH Batters"
LH_TITLE = "Heat Map vs. LH Batters"


def _iter_strings(node: object) -> Iterator[str]:
    """Yield every string found in a Dash component tree."""
    if isinstance(node, str):
        yield node
        return
    if isinstance(node, (list, tuple)):
        for child in node:
            yield from _iter_strings(child)
        return
    children = getattr(node, "children", None)
    if children is not None:
        yield from _iter_strings(children)


def test_web_layout_uses_new_heatmap_titles() -> None:
    from python_app import app as app_module

    strings = set(_iter_strings(app_module.app.layout))
    assert RH_TITLE in strings
    assert LH_TITLE in strings


def test_heatmap_layout_fragments_use_new_titles() -> None:
    from python_app.features import heatmaps

    right = set(_iter_strings(heatmaps.layout_right()))
    left = set(_iter_strings(heatmaps.layout_left()))
    assert RH_TITLE in right
    assert LH_TITLE in left


def test_pdf_heatmap_titles_match() -> None:
    from python_app.features import pdf_export

    assert pdf_export._HEATMAP_TITLES == [RH_TITLE, LH_TITLE]
