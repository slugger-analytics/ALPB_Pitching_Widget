"""Responsive-layout tests.

On phones every Bootstrap column must stack to full width, so each ``dbc.Col``
in the main layout tree must declare ``xs=12`` (the ``md=*`` breakpoints then
restore the multi-column desktop layout).
"""

from __future__ import annotations

from typing import Iterator

import dash_bootstrap_components as dbc
from dash.development.base_component import Component


def _iter_components(node: object) -> Iterator[Component]:
    """Yield every Dash Component in a layout tree (depth-first)."""
    if isinstance(node, Component):
        yield node
        children = getattr(node, "children", None)
        if children is not None:
            yield from _iter_components(children)
    elif isinstance(node, (list, tuple)):
        for child in node:
            yield from _iter_components(child)


def test_every_col_stacks_full_width_on_mobile() -> None:
    from python_app import app as app_module

    cols = [n for n in _iter_components(app_module.app.layout) if isinstance(n, dbc.Col)]

    assert cols, "expected at least one dbc.Col in the layout"
    for col in cols:
        assert getattr(col, "xs", None) == 12, (
            f"dbc.Col missing xs=12 (got xs={getattr(col, 'xs', None)!r})"
        )
