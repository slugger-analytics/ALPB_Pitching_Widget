# ALPB-Pitching-Widget1

The Atlantic League of Professional Baseball (ALPB) is the highest-level professional baseball league outside of MLB. This project aims to develop a standalone Shiny App widget in R, mirroring the existing ALPB hitting widget but tailored for pitchers. The app will allow users to analyze and track key pitching metrics such as Earned Run Average (ERA) and Walks and Hits per Inning Pitched (WHIP). Designed for coaches, recruiters, and fans, it will provide valuable insights into pitchers' performances.

Hosted using Shiny App, users can select a pitcher and the app will display several key graphs and tables: General pitcher info (name, team name, height, throw hand, etc), Season Stats, and Break v. Velocity, Induced Vertical vs. Horizontal Break, Strike Zone, Pitch Type Percentages, and a PDF generation graph. 


Ultimately, we hope that users such as pitchers, coaches, and front office members can easily access all this data and print it out on a small sheet of paper to help make insightful decisions throughout the game, in their analyses, or just for interest.

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
