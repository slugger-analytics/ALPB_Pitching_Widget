"""
Centralized configuration for the ALPB Pitching Widget.

Single source of truth for API keys, URLs, season settings,
pitch type colors, and axis labels used across all modules.
"""

# ── Pointstreak API ──────────────────────────────────────────────────────────
POINTSTREAK_API_KEY = "vIpQsngDfc6Y7WVgAcTt"
POINTSTREAK_BASE_URL = "https://api.pointstreak.com/baseball"
LEAGUE_ID = "174"

# ── ALPB Trackman API ────────────────────────────────────────────────────────
ALPB_API_KEY = "IuHgm3smV65kbC6lMlMLz80DOeEkGSiV6USoQhvZ"
ALPB_BASE_URL = "https://1ywv9dczq5.execute-api.us-east-2.amazonaws.com/ALPBAPI"

# ── Season / roster filters ─────────────────────────────────────────────────
DEFAULT_SEASON_ID = "34104"
EXCLUDED_TEAMS = {"Staten Island Ferry Hawks", "Long Island Black Sox"}

# ── Pitch type colors (shared by Plotly graphs and matplotlib PDF) ───────────
PITCH_COLORS = {
    "Fastball": "red",
    "Four-Seam": "red",
    "Changeup": "blue",
    "ChangeUp": "blue",
    "Sinker": "green",
    "Curveball": "brown",
    "Slider": "purple",
    "Splitter": "black",
    "Cutter": "pink",
    "Untagged": "gray",
}

# ── Axis display labels ─────────────────────────────────────────────────────
AXIS_LABELS = {
    "induced_vert_break": "Induced Vertical Break (inches)",
    "horz_break": "Horizontal Break (inches)",
    "rel_speed": "Velocity (mph)",
}

AXIS_SHORT_LABELS = {
    "induced_vert_break": "Ind. Vert. Break",
    "horz_break": "Horz. Break",
    "rel_speed": "Velocity",
}

# ── UI styling ───────────────────────────────────────────────────────────────
TABLE_HEADER_COLOR = "#17a2b8"

TABLE_STYLE_HEADER = {
    "backgroundColor": TABLE_HEADER_COLOR,
    "color": "white",
    "fontWeight": "bold",
}

TABLE_STYLE_CELL = {
    "textAlign": "center",
    "padding": "5px",
    "fontSize": "12px",
}

TABLE_STYLE_DATA_CONDITIONAL = [
    {"if": {"row_index": "odd"}, "backgroundColor": "#f9f9f9"},
]

# ── Parallel fetch settings ──────────────────────────────────────────────────
MAX_WORKERS = 8
