"""
Shared UI styling helpers.

Reusable layout components and Dash DataTable style dicts.  Every visual
element here uses the brand palette from :mod:`python_app.config` so the
web UI matches the PDF export.

CSS styling lives in ``assets/brand.css`` (auto-loaded by Dash).
"""

from __future__ import annotations

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


def styled_table(df, **kwargs) -> dash_table.DataTable:
    """Create a Dash DataTable with the app's standard styling."""
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        style_table={"overflowX": "auto"},
        style_header=TABLE_STYLE_HEADER,
        style_cell=TABLE_STYLE_CELL,
        style_data_conditional=TABLE_STYLE_DATA_CONDITIONAL,
        **kwargs,
    )
