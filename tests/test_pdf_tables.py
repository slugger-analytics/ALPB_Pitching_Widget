"""Tests for the PDF pitch-usage table row-max highlight.

The PDF export must paint the row-max cell with the exact same navy background
as the web table (both sourced from ``python_app.config.HIGHLIGHT_BG``).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd

from python_app.config import HIGHLIGHT_BG
from python_app.features.pdf_export import _render_table


def test_pdf_row_max_cell_uses_highlight_bg() -> None:
    df = pd.DataFrame({"Count": ["0 - 0"], "FB": [70.0], "SL": [30.0]})

    fig = plt.figure()
    ax = fig.add_subplot(111)
    try:
        _render_table(ax, df, highlight_row_max=True)

        assert ax.tables, "expected a rendered matplotlib table"
        tbl = ax.tables[0]

        # Row 0 is the header; data row 1 / col 1 is the "FB" max cell.
        max_cell = tbl[(1, 1)]
        assert mcolors.to_hex(max_cell.get_facecolor()) == HIGHLIGHT_BG.lower()

        # The non-max "SL" cell (col 2) must NOT carry the highlight.
        other_cell = tbl[(1, 2)]
        assert mcolors.to_hex(other_cell.get_facecolor()) != HIGHLIGHT_BG.lower()
    finally:
        plt.close(fig)
