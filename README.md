# ALPB Pitching Widget

The **Atlantic League of Professional Baseball (ALPB) Pitching Widget** is an interactive web application for analyzing and tracking pitching performance metrics. Designed for **coaches, recruiters, front office staff, and fans**, this app offers clear visualizations and data summaries to support informed decision-making.

## Features

- **Pitcher Profile**: Basic info including name, team, height, throwing hand, and more.
- **Season Statistics**: Earned Run Average (ERA), WHIP, strikeouts, and other season-long metrics.
- **Visualizations**:
  - Break vs. Velocity
  - Induced Vertical vs. Horizontal Break
  - Strike Zone Heatmaps
  - Pitch Type Percentages
- **PDF Export**: Create a printable one-sheet pitcher report for scouting or game prep.

## Data APIs

- **Trackman** – Pitch-by-pitch data including spin rate, pitch type, velocity, break, and more.
- **Pointstreak** – Aggregated season stats such as ERA, innings pitched, and strikeouts.

Data is accessed via their APIs using Python's `requests` library, with pagination and caching for performance.

## Python App (Dash)

The Python version lives in `python_app/` and uses [Dash](https://dash.plotly.com/) (by Plotly) as the web framework.

### Quick Start (From Download / Clone)

```bash
git clone https://github.com/tanx3036/SLUGGER-Pitching-Widget.git
cd SLUGGER-Pitching-Widget
python3 -m venv .venv
source .venv/bin/activate
pip install -r python_app/requirements.txt
python python_app/app.py
```

The app will be available at `http://localhost:8050`.

### Run Again Later

```bash
cd SLUGGER-Pitching-Widget
source .venv/bin/activate
python python_app/app.py
```

### Project Structure

```
python_app/
├── app.py                        # Main Dash application
├── requirements.txt              # Python dependencies
├── api/
│   ├── pointstreak.py            # Pointstreak roster & stats API
│   └── alpb.py                   # ALPB Trackman pitch data API
├── visualizations/
│   ├── graphs.py                 # Break/velocity scatter plots
│   └── heatmap.py                # Strike zone heatmaps
├── analysis/
│   └── pitch_split.py            # Pitch usage by count
└── reports/
    └── pdf_report.py             # PDF scouting report generation
```

### Technology Mapping (R → Python)

| R Package / Tool     | Python Equivalent        |
|----------------------|--------------------------|
| Shiny                | Dash                     |
| ggplot2              | Plotly / Matplotlib      |
| httr + jsonlite      | requests                 |
| dplyr / tidyr        | pandas                   |
| DT                   | dash_table.DataTable     |
| MASS::kde2d          | scipy.stats.gaussian_kde |
| rmarkdown            | matplotlib PdfPages      |
| shinyjs              | Dash callbacks           |
| cowplot / patchwork   | plotly subplots           |

## Legacy R App (Shiny)

The original R Shiny version remains in the `newShiny/` directory.

### R Installation

```r
install.packages(c(
  "DT", "MASS", "cowplot", "dplyr", "ggplot2", "hash", "httr",
  "jsonlite", "patchwork", "rmarkdown", "rsconnect", "shiny",
  "shinyjs", "tibble", "tidyr"
))
