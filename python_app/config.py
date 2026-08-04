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

# ── ALPB Trackman API ────────────────────────────────────────────────────────
ALPB_API_KEY = os.getenv("ALPB_API_KEY", "")
ALPB_BASE_URL = os.getenv(
    "ALPB_BASE_URL",
    "https://1ywv9dczq5.execute-api.us-east-2.amazonaws.com/ALPBAPI",
)

# ── Season / roster filters ─────────────────────────────────────────────────
EXCLUDED_TEAMS: set[str] = {"California Dogecoin", "Long Island Black Sox"}

# ── Brand colours (shared by Dash UI and PDF export) ─────────────────────────
BRAND_NAVY:       str = "#002D72"
BRAND_RED:        str = "#C8102E"
BRAND_LIGHT_GRAY: str = "#f5f6fa"
BRAND_MID_GRAY:   str = "#dcdde1"

# Legacy alias used by existing code
TABLE_HEADER_COLOR: str = BRAND_NAVY

# Row-max highlight (pitch-usage table) — a bold navy fill with white text so the
# most-thrown pitch per count is unmistakable. Shared by the Dash web table and
# the matplotlib PDF export so both render identically.
HIGHLIGHT_BG:   str = BRAND_NAVY   # "#002D72"
HIGHLIGHT_TEXT: str = "#FFFFFF"

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

# ── Batter-side filter ───────────────────────────────────────────────────────
# "All" is the pass-through sentinel; the labels map concrete sides to the
# short "vs RHB" / "vs LHB" text shown in the UI radio and empty-state messages.
BATTER_SIDE_ALL: str = "All"
BATTER_SIDE_LABELS: dict[str, str] = {"Right": "vs RHB", "Left": "vs LHB"}

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

# ── iScore API ───────────────────────────────────────────────────────────────
ISCORE_BASE_URL = os.getenv(
    "ISCORE_BASE_URL",
    "https://api.microservices.iscoresports.com/api",
)
ISCORE_LEAGUE_GUID = os.getenv("ISCORE_LEAGUE_GUID", "")
ISCORE_SEASON_GUID = os.getenv("ISCORE_SEASON_GUID", "")
ISCORE_SEASON_NAME = os.getenv("ISCORE_SEASON_NAME", "ALPB 2026")

# ── Parallel-fetch settings ──────────────────────────────────────────────────
MAX_WORKERS: int = 8

# ── Cache refresh TTLs ───────────────────────────────────────────────────────
# The Fargate container is long-lived (days), so the roster and negative ALPB-id
# lookups expire and refresh in place — newly signed pitchers must surface
# without a container restart. Both are env-overridable for tuning.
ROSTER_TTL_SECONDS: int = int(os.getenv("ROSTER_TTL_SECONDS", "900"))
NEGATIVE_ID_TTL_SECONDS: int = int(os.getenv("NEGATIVE_ID_TTL_SECONDS", "1800"))

# Pitch-level and season-stat caches expire too, so a pitcher who was already
# viewed still picks up the pitches he threw today. An empty pitch result
# expires sooner than a populated one — re-testing it costs a single request,
# while refetching a populated pitcher re-pages his whole season.
PITCH_DATA_TTL_SECONDS: int = int(os.getenv("PITCH_DATA_TTL_SECONDS", "1800"))
NEGATIVE_PITCH_DATA_TTL_SECONDS: int = int(os.getenv("NEGATIVE_PITCH_DATA_TTL_SECONDS", "300"))
SEASON_STATS_TTL_SECONDS: int = int(os.getenv("SEASON_STATS_TTL_SECONDS", "1800"))

# A failed refetch keeps serving the value already cached, but the entry is
# restamped to expire again after this short backoff — otherwise every later
# view would issue its own upstream request for as long as the API is degraded.
REFETCH_BACKOFF_SECONDS: int = int(os.getenv("REFETCH_BACKOFF_SECONDS", "60"))
