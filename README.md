# ALPB-Pitching-Widget1

The Atlantic League of Professional Baseball (ALPB) Pitching Widget is an interactive Shiny App developed in R that allows users to explore and analyze key pitching metrics for ALPB pitchers. This tool is designed for coaches, recruiters, front office personnel, and fans to track pitcher performance in real-time or over the season.

#Overview
The ALPB is the highest-level professional baseball league outside of MLB, and this tool mirrors our existing hitting widget — but tailored for pitchers. The app includes visuals and data summaries that help evaluate performance and pitch characteristics.

#Features
1. Pitcher Profile: General information including name, team, height, throwing hand, etc.
2. Season Stats: Key performance metrics such as ERA, WHIP, strikeouts, etc.

Visualizations:
3. Break vs. Velocity //
4. Induced Vertical Break vs. Horizontal Break//
5. Strike Zone Map
6. Pitch Type Percentages
7. PDF Generation: Generate a printable one-sheet summary of a pitcher's data.

install.packages(c(
  "DT",
  "MASS",
  "cowplot",
  "dplyr",
  "ggplot2",
  "hash",
  "httr",
  "jsonlite",
  "patchwork",
  "rmarkdown",
  "rsconnect",
  "shiny",
  "shinyjs",
  "tibble",
  "tidyr"
))
