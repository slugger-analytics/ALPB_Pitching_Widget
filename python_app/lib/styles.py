"""
Shared UI styling helpers.

Reusable card components and Dash DataTable style dicts so that every
feature file doesn't redefine the same Bootstrap patterns.
"""

from dash import html, dash_table

from python_app.config import (
    TABLE_STYLE_HEADER,
    TABLE_STYLE_CELL,
    TABLE_STYLE_DATA_CONDITIONAL,
)


def info_card(title, body):
    """Bootstrap card with an info-colored header bar."""
    return html.Div(
        className="card",
        children=[
            html.Div(
                title,
                className="card-header bg-info text-white text-center fw-bold",
                style={"paddingTop": "5px", "paddingBottom": "5px"},
            ),
            html.Div(
                html.Div(body, style={"textAlign": "center", "width": "100%"}),
                className="card-body d-flex justify-content-center align-items-center",
            ),
        ],
    )


def styled_table(df, **kwargs):
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
