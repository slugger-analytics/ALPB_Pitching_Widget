"""
Shared UI styling helpers.

Reusable layout components and Dash DataTable style dicts.  Every visual
element here uses the brand palette from :mod:`python_app.config` so the
web UI matches the PDF export.

CSS styling lives in ``assets/brand.css`` (auto-loaded by Dash).
"""

from __future__ import annotations

import pandas as pd
from dash import dash_table, html

from python_app.config import (
    TABLE_STYLE_CELL,
    TABLE_STYLE_DATA_CONDITIONAL,
    TABLE_STYLE_HEADER,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Layout components
# ═══════════════════════════════════════════════════════════════════════════════

def info_card(title: str, body) -> html.Div:
    """Card with a navy-branded header — matches the PDF section style."""
    return html.Div(
        className="card-navy",
        children=[
            html.Div(title, className="card-header"),
            html.Div(
                html.Div(body, style={"textAlign": "center", "width": "100%"}),
                className="card-body d-flex justify-content-center align-items-center",
            ),
        ],
    )


def section_label(text: str) -> html.Div:
    """Section heading that mirrors the PDF ``_section_label``."""
    return html.Div(text, className="section-label")


def _row_max_highlight_rules(
    df: pd.DataFrame,
    *,
    start_col: int = 1,
) -> list[dict]:
    """Build Dash DataTable conditional rules for row-wise max numeric values."""
    rules: list[dict] = []
    if df.empty or len(df.columns) <= start_col:
        return rules

    for row_idx in range(len(df)):
        numeric_vals: list[tuple[str, float]] = []
        for col in df.columns[start_col:]:
            val = pd.to_numeric(df.iloc[row_idx][col], errors="coerce")
            if pd.notna(val):
                numeric_vals.append((str(col), float(val)))
        if not numeric_vals:
            continue

        row_max = max(v for _, v in numeric_vals)
        for col, val in numeric_vals:
            if abs(val - row_max) > 1e-9:
                continue
            rules.append(
                {
                    "if": {"row_index": row_idx, "column_id": col},
                    "backgroundColor": "#E6EEF9",
                    "color": "#002D72",
                    "fontWeight": "bold",
                }
            )
    return rules


def styled_table(
    df: pd.DataFrame,
    *,
    uppercase_columns: bool = False,
    highlight_row_max_from_col: int | None = None,
    **kwargs,
) -> dash_table.DataTable:
    """Create a Dash DataTable with the app's standard styling."""
    display = df.copy()
    if uppercase_columns:
        display.columns = [str(c).upper() for c in display.columns]

    extra_rules = kwargs.pop("style_data_conditional", [])
    style_data_conditional = list(TABLE_STYLE_DATA_CONDITIONAL)
    if highlight_row_max_from_col is not None:
        style_data_conditional.extend(
            _row_max_highlight_rules(display, start_col=highlight_row_max_from_col)
        )
    style_data_conditional.extend(extra_rules)

    return dash_table.DataTable(
        data=display.to_dict("records"),
        columns=[{"name": c, "id": c} for c in display.columns],
        style_table={"overflowX": "auto"},
        style_header=TABLE_STYLE_HEADER,
        style_cell=TABLE_STYLE_CELL,
        style_data_conditional=style_data_conditional,
        **kwargs,
    )
