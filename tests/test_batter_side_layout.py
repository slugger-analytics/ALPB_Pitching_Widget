"""Layout tests for the "Batter Side:" RadioItems control.

Walks ``app.layout`` (same pattern as ``test_layout.py``) to assert the new
control exists with the right options/default, sits in an ``xs=12 md=3`` column,
and that the four controls-row columns still sum to a full 12-wide Bootstrap row.
"""

from __future__ import annotations

from typing import Iterator

import dash_bootstrap_components as dbc
from dash import dcc
from dash.development.base_component import Component


def _iter_components(node: object) -> Iterator[Component]:
    if isinstance(node, Component):
        yield node
        children = getattr(node, "children", None)
        if children is not None:
            yield from _iter_components(children)
    elif isinstance(node, (list, tuple)):
        for child in node:
            yield from _iter_components(child)


def _direct_children(node: object) -> list:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def _has_id(node: object, target_id: str) -> bool:
    return any(getattr(n, "id", None) == target_id for n in _iter_components(node))


def test_batter_side_radio_options_and_default() -> None:
    from python_app import app as app_module

    radios = [
        n
        for n in _iter_components(app_module.app.layout)
        if isinstance(n, dcc.RadioItems) and getattr(n, "id", None) == "batter-side"
    ]
    assert len(radios) == 1, "expected exactly one batter-side RadioItems"
    radio = radios[0]

    assert [o["value"] for o in radio.options] == ["All", "Right", "Left"]
    labels = " ".join(o["label"] for o in radio.options)
    assert "vs RHB" in labels
    assert "vs LHB" in labels
    assert radio.value == "All"


def test_batter_side_col_breakpoints() -> None:
    from python_app import app as app_module

    layout = app_module.app.layout
    cols = [n for n in _iter_components(layout) if isinstance(n, dbc.Col)]

    # The control column holds the batter-side radio but not the other controls.
    control_cols = [
        c for c in cols if _has_id(c, "batter-side") and not _has_id(c, "break-type")
    ]
    assert len(control_cols) == 1
    col = control_cols[0]
    assert col.xs == 12
    assert col.md == 3


def test_controls_row_cols_sum_to_twelve() -> None:
    from python_app import app as app_module

    layout = app_module.app.layout
    cols = [n for n in _iter_components(layout) if isinstance(n, dbc.Col)]
    control_col = next(
        c for c in cols if _has_id(c, "batter-side") and not _has_id(c, "break-type")
    )

    controls_row = None
    for row in _iter_components(layout):
        if isinstance(row, dbc.Row) and any(
            child is control_col for child in _direct_children(row)
        ):
            controls_row = row
            break
    assert controls_row is not None, "controls row containing batter-side not found"

    row_cols = [c for c in _direct_children(controls_row) if isinstance(c, dbc.Col)]
    assert len(row_cols) == 4
    assert sum(c.md for c in row_cols) == 12
