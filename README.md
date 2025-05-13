# ALPB Pitching Widget

The **Atlantic League of Professional Baseball (ALPB) Pitching Widget** is an interactive Shiny App built in R for analyzing and tracking pitching performance metrics. Designed for **coaches, recruiters, front office staff, and fans**, this app offers clear visualizations and data summaries to support informed decision-making.

##  Features

- **Pitcher Profile**: Basic info including name, team, height, throwing hand, and more.
- **Season Statistics**: Earned Run Average (ERA), WHIP, strikeouts, and other season-long metrics.
- **Visualizations**:
  - Break vs. Velocity
  - Induced Vertical vs. Horizontal Break
  - Strike Zone plots
  - Pitch Type Percentages
- **PDF Export**: Create a printable one-sheet pitcher report for scouting or game prep.

## Data APIs

- **Trackman** – Pitch-by-pitch data including spin rate, pitch type, velocity, break, and more.
- **Pointstreak** – Aggregated season stats such as ERA, innings pitched, and strikeouts.

We accessed data via their APIs using Postman and R's `httr` and `jsonlite` packages, implementing pagination and caching to improve performance.


## Installation

To run the app locally, install the following R packages:

```r
install.packages(c(
  "DT", "MASS", "cowplot", "dplyr", "ggplot2", "hash", "httr",
  "jsonlite", "patchwork", "rmarkdown", "rsconnect", "shiny",
  "shinyjs", "tibble", "tidyr"
))

