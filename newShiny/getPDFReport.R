library(rmarkdown)
library(ggplot2)
library(patchwork)
library(cowplot)

#PDF generation when there is no data
get_no_data_pdf <- function(name) {
  report_header <- list(name = name)
  output_path <- tempfile(fileext = ".pdf")
  rmarkdown::render(
    input = file.path(getwd(), "PDFReportFormatNoData.Rmd"),
    output_format = "pdf_document",
    output_file = output_path,
    params = list(
      report_header = report_header
    ),
    envir = new.env(parent = globalenv())
  )
  
  return(output_path)
}

#PDF generation when there is no ALPB data but there is pointstreak data
get_no_ALPB_pdf <- function(pointstreak, name) {
  report_header <- list(name = name)
  
  output_path <- tempfile(fileext = ".pdf")
  
  
  source('getSeasonStats.R')
  #generate season stats from poinstreak
  season_stats <- get_pitching_stats_only(pointstreak)
  
  rmarkdown::render(
    input = file.path(getwd(), "PDFReportFormatBare.Rmd"),
    output_format = "pdf_document",
    output_file = output_path,
    params = list(
      report_header = report_header,
      season_stats = season_stats
    ),
    envir = new.env(parent = globalenv())
  )
  
  
  
  return(output_path)
  
}

#PDF generation when there is no Poinstreak data but there is ALPB data
get_no_poinstreak_pdf <- function(df, name, pitch_type) {
  report_header <- list(name = name)
  
  output_path <- tempfile(fileext = ".pdf")
  #Build the three break plots
  source('getGraphs.R')
  HI_graph <- build_graph_with_title(df, "horz_break", "induced_vert_break", "auto_pitch_type")
  VI_graph <- build_graph_with_title(df, "rel_speed", "induced_vert_break", "auto_pitch_type")
  VH_graph <- build_graph_with_title(df, "rel_speed", "horz_break", "auto_pitch_type")
  
  #combine them into one row and keep one legend
  combined_plot <- HI_graph + VI_graph + VH_graph +
    plot_layout(ncol = 3,
                guides = "collect") &
    theme(
      legend.position = "bottom",
      legend.title = element_text(size = 7),
      legend.text = element_text(size = 6)
    )
  
  #Filter data so that there are no undefined pitches
  df <- df %>%
    filter(!is.na(.data[[pitch_type]]), .data[[pitch_type]] != "Undefined")
  
  source('pitchSplit.R')
  #create pitch split table
  splitDF <- get_pitch_type_percentages(df, pitch_type)
  
  
  source('getHeatMap.R')
  unique_values <- unique(df[[pitch_type]])
  heatmaps_list_rhp <- list()
  
  # Loop through each pitch type that the batter has seen and call the heatmap building function. Store results in a list
  
  for (type in unique_values) {
    filtered_df <- df[df[[pitch_type]] == type, ]
    # heatmaps_list_rhp[type] <- build_all_three(df)
    heatmaps_list_rhp[[type]] <- build_all_three(filtered_df, type)
    
  }
  
  # combine all of the heatmaps together using cowplot to arrange them in a grid
  
  heatmaps_row_rhp <- cowplot::plot_grid(plotlist = heatmaps_list_rhp, ncol = 1)
  
  
  rmarkdown::render(
    input = file.path(getwd(), "PDFReportFormatNoPoinstreak.Rmd"),
    output_format = "pdf_document",
    output_file = output_path,
    params = list(
      report_header = report_header,
      combined_plot = combined_plot,
      pitch_split = splitDF,
      heatmaps_row_rhp = heatmaps_list_rhp
    ),
    envir = new.env(parent = globalenv())
  )
  
  
  
  return(output_path)
}

#generate PDF when there is ALPB and Pointstreak data
get_all_pdf <- function(pointstreak, df, name, pitch_type) {

  report_header <- list(name = name)

  output_path <- tempfile(fileext = ".pdf")
  #Build the three break plots
  source('getGraphs.R')
  HI_graph <- build_graph_with_title(df, "horz_break", "induced_vert_break", "auto_pitch_type")
  VI_graph <- build_graph_with_title(df, "rel_speed", "induced_vert_break", "auto_pitch_type")
  VH_graph <- build_graph_with_title(df, "rel_speed", "horz_break", "auto_pitch_type")

  #combine them into one row and keep one legend
  combined_plot <- HI_graph + VI_graph + VH_graph +
    plot_layout(ncol = 3,
                guides = "collect") &
    theme(
      legend.position = "bottom",
      legend.title = element_text(size = 7),
      legend.text = element_text(size = 6)
    )
  
  #Filter data so that there are no undefined pitches
  df <- df %>%
    filter(!is.na(.data[[pitch_type]]), .data[[pitch_type]] != "Undefined")
  
  source('pitchSplit.R')
  #create pitch split table
  splitDF <- get_pitch_type_percentages(df, pitch_type)
  
  
  source('getHeatMap.R')
  unique_values <- unique(df[[pitch_type]])
  heatmaps_list_rhp <- list()

  # Loop through each pitch type that the batter has seen and call the heatmap building function. Store results in a list

  for (type in unique_values) {
    filtered_df <- df[df[[pitch_type]] == type, ]
    heatmaps_list_rhp[[type]] <- build_all_three(filtered_df, type)

  }

  # combine all of the heatmaps together using cowplot to arrange them in a grid

  heatmaps_row_rhp <- cowplot::plot_grid(plotlist = heatmaps_list_rhp, ncol = 1)
  
  source('getSeasonStats.R')
  season_stats <- get_pitching_stats_only(pointstreak)
  
  rmarkdown::render(
    input = file.path(getwd(), "PDFReportFormat.Rmd"),
    output_format = "pdf_document",
    output_file = output_path,
    params = list(
      report_header = report_header,
      combined_plot = combined_plot,
      pitch_split = splitDF,
      heatmaps_row_rhp = heatmaps_list_rhp,
      season_stats = season_stats
    ),
    envir = new.env(parent = globalenv())
  )



  return(output_path)


}