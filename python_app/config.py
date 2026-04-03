"""
Centralised configuration for the ALPB Pitching Widget.

Single source of truth for API keys, URLs, season settings,
pitch-type colours, axis labels, and UI styling constants.

The colour palette defined here is shared by **both** the Dash web UI
and the matplotlib PDF export so they always look consistent.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Optional for environments that inject vars directly.
    load_dotenv = None


def _load_dotenv_fallback(dotenv_path: Path) -> None:
    """Minimal .env loader for local runs when python-dotenv is unavailable."""
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


_dotenv_path = Path(__file__).resolve().parents[1] / ".env"
if load_dotenv is not None:
    # Load repo-root .env for local runs (python python_app/app.py).
    load_dotenv(_dotenv_path, override=False)
else:
    _load_dotenv_fallback(_dotenv_path)

# ── Pointstreak API ──────────────────────────────────────────────────────────
POINTSTREAK_API_KEY = os.getenv("POINTSTREAK_API_KEY", "")
POINTSTREAK_BASE_URL = os.getenv(
    "POINTSTREAK_BASE_URL",
    "https://api.pointstreak.com/baseball",
)
LEAGUE_ID = os.getenv("POINTSTREAK_LEAGUE_ID", "174")

# ── ALPB Trackman API ────────────────────────────────────────────────────────
ALPB_API_KEY = os.getenv("ALPB_API_KEY", "")
ALPB_BASE_URL = os.getenv(
    "ALPB_BASE_URL",
    "https://1ywv9dczq5.execute-api.us-east-2.amazonaws.com/ALPBAPI",
)

# ── Season / roster filters ─────────────────────────────────────────────────
DEFAULT_SEASON_ID = os.getenv("DEFAULT_SEASON_ID", "34102")
EXCLUDED_TEAMS: set[str] = {"California Dogecoin", "Long Island Black Sox"}

# ── Brand colours (shared by Dash UI and PDF export) ─────────────────────────
BRAND_NAVY:       str = "#002D72"
BRAND_RED:        str = "#C8102E"
BRAND_LIGHT_GRAY: str = "#f5f6fa"
BRAND_MID_GRAY:   str = "#dcdde1"

# Legacy alias used by existing code
TABLE_HEADER_COLOR: str = BRAND_NAVY

# ── Pitch-type colours (shared by Plotly graphs and matplotlib PDF) ──────────
PITCH_COLORS: dict[str, str] = {
    "Fastball":   "red",
    "Four-Seam":  "red",
    "Changeup":   "blue",
    "ChangeUp":   "blue",
    "Sinker":     "green",
    "Curveball":  "brown",
    "Slider":     "purple",
    "Splitter":   "black",
    "Cutter":     "pink",
    "Untagged":   "gray",
}

# ── Axis display labels ─────────────────────────────────────────────────────
AXIS_LABELS: dict[str, str] = {
    "induced_vert_break": "Induced Vertical Break (inches)",
    "horz_break":         "Horizontal Break (inches)",
    "rel_speed":          "Velocity (mph)",
}

AXIS_SHORT_LABELS: dict[str, str] = {
    "induced_vert_break": "Ind. Vert. Break",
    "horz_break":         "Horz. Break",
    "rel_speed":          "Velocity",
}

# ── Dash DataTable styling ───────────────────────────────────────────────────
TABLE_STYLE_HEADER: dict = {
    "backgroundColor": BRAND_NAVY,
    "color": "white",
    "fontWeight": "bold",
}

TABLE_STYLE_CELL: dict = {
    "textAlign": "center",
    "padding": "5px",
    "fontSize": "12px",
}

TABLE_STYLE_DATA_CONDITIONAL: list[dict] = [
    {"if": {"row_index": "odd"}, "backgroundColor": BRAND_LIGHT_GRAY},
]

# ── Parallel-fetch settings ──────────────────────────────────────────────────
MAX_WORKERS: int = 8
