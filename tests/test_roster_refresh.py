"""Tests for the roster-refresh Interval wiring (P1 app layer).

The Interval must poll fast until the roster first loads, then slow to a
periodic cadence — and it must never be disabled, so the roster keeps
refreshing for the life of the container.
"""

from __future__ import annotations

from typing import Iterator

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


def test_polling_slows_once_teams_loaded() -> None:
    from python_app import app as app_module

    only_sentinel = [{"label": "All Teams", "value": app_module._ALL_TEAMS}]
    assert app_module.slow_roster_polling(only_sentinel) == app_module.ROSTER_REFRESH_FAST_MS

    with_teams = only_sentinel + [
        {"label": "High Point Rockers", "value": "High Point Rockers"},
    ]
    assert app_module.slow_roster_polling(with_teams) == app_module.ROSTER_REFRESH_SLOW_MS
    assert app_module.ROSTER_REFRESH_SLOW_MS > app_module.ROSTER_REFRESH_FAST_MS


def test_roster_interval_is_never_disabled() -> None:
    from python_app import app as app_module

    intervals = [
        n
        for n in _iter_components(app_module.app.layout)
        if getattr(n, "id", None) == "roster-refresh"
    ]
    assert intervals, "roster-refresh Interval not found in layout"
    assert getattr(intervals[0], "disabled", False) is False
