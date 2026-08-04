"""Guards that every outbound HTTP call carries a socket timeout.

gunicorn runs ``--workers 1 --threads 2``, so a request left on requests' default
timeout of ``None`` can hang forever and take the whole widget down with it. The
pitch-data and season-stat TTLs make these calls recur, so this must stay true.
"""

from __future__ import annotations

import ast
import inspect

import python_app.lib.api as api

_SESSIONS = {"_alpb_session", "_iscore_session"}


def _session_calls() -> list[ast.Call]:
    """Every ``<session>.get(...)`` call node in :mod:`python_app.lib.api`."""
    tree = ast.parse(inspect.getsource(api))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in _SESSIONS
    ]


def test_every_session_get_passes_a_timeout() -> None:
    calls = _session_calls()
    assert calls, "no session .get() calls found — the guard would be vacuous"
    for call in calls:
        kwargs = {kw.arg for kw in call.keywords}
        assert "timeout" in kwargs, f"{api.__name__}:{call.lineno} has no timeout"


def test_alpb_and_iscore_use_the_same_timeout() -> None:
    """Both feeds share one connect/read budget — no per-call special cases."""
    timeouts = set()
    for call in _session_calls():
        value = next(kw.value for kw in call.keywords if kw.arg == "timeout")
        timeouts.add(ast.literal_eval(value))
    assert timeouts == {(5, 15)}
