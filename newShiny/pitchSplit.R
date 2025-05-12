library(dplyr)
library(tidyr)
library(tibble)
library(ggplot2)
library(cowplot)

# This function calculates the percentage of each pitch type thrown in every ball-strike count
# using either Trackman or human tagging, as specified by the 'tag' parameter
get_pitch_type_percentages <- function(pitch_data, tag) {
  
  # Filter out rows with missing count info or undefined pitch types
  pitch_data <- pitch_data %>%
    filter(!is.na(balls) & !is.na(strikes) & !is.na(.data[[tag]]) & .data[[tag]] != "Undefined")
  
  # If there's no usable data after filtering, return an empty data frame with expected columns
  if (nrow(pitch_data) == 0) {
    return(data.frame(Pitch_Type = character(0), Count = character(0), Percentage = numeric(0)))
  }
  
  # Create a "Count" column combining balls and strikes in the format "B-S"
  pitch_data$Count <- paste(pitch_data$balls, "-", pitch_data$strikes)
  
  # - Count the number of each pitch type thrown in each count
  pitch_summary <- pitch_data %>%
    group_by(Count, .data[[tag]]) %>%
    summarise(pitch_count = n(), .groups = "drop") %>%
    group_by(Count) %>%
    mutate(total_pitches_in_count = sum(pitch_count)) %>%
    ungroup() %>%
    spread(key = .data[[tag]], value = pitch_count, fill = 0) %>%
    # Round percentages to 1 decimal place
    mutate(across(-Count & -total_pitches_in_count, ~ round(. / total_pitches_in_count * 100, 1))) %>%
    arrange(Count) %>%
    dplyr::select(-any_of("total_pitches_in_count"))
  
  return(pitch_summary)
  
}