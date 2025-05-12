library(ggplot2)
library(shiny)
# library(dplyr)  # Optional
library(hash)

# maps that hold graph labels depending on axis
map_with_label <- hash() 
map_with_label[["induced_vert_break"]] <- "Induced Vertical Break (inches)"
map_with_label[["horz_break"]] <- "Horizontal Break (inches)"
map_with_label[["rel_speed"]] <- "Velocity (mph)"

map_without_label <- hash() 
map_without_label[["induced_vert_break"]] <- "Induced Vertical Break"
map_without_label[["horz_break"]] <- "Horizontal Break"
map_without_label[["rel_speed"]] <- "Velocity"

#create a graph with given x and y axis, as well as a tag
#x and y axis must be one of the above keys
build_graph <- function (filtered_df, x_axis, y_axis, tag) {
  
  #create a new column in data frame called tag that converts all untagged pitches to be call untagged
  if (!is.null(filtered_df) && nrow(filtered_df) > 0 &&
      x_axis %in% names(filtered_df) &&
      y_axis %in% names(filtered_df)) {
    
    filtered_df$TagStatus <- ifelse(filtered_df[[tag]] == "Undefined" | is.na(filtered_df[[tag]]),
                           "Untagged", as.character(filtered_df[[tag]]))
    #create plot
    plot <- ggplot(filtered_df, aes(x = .data[[x_axis]], y = .data[[y_axis]], color = TagStatus)) +
      geom_point(alpha = 0.7, size = 2) +
      labs(
        x = map_with_label[[x_axis]],
        y = map_with_label[[y_axis]]) +
      theme_minimal() +
      #color coding the pitches
      scale_color_manual("Pitch Tag", values = c(
        "Fastball" = "red", 
        "Four-Seam" = "red",
        "Changeup" = "blue", 
        "ChangeUp" = "blue", 
        "Sinker" = "green", 
        "Curveball" = "brown", 
        "Slider" = "purple", 
        "Splitter" = "black", 
        "Cutter" = "pink",
        "Untagged" = "gray"
      ))
  }
  return(plot)
}

#for PDF -- builds graph with title
build_graph_with_title <- function (filtered_df, x_axis, y_axis, tag) {
  
  #create a new column in data frame called tag that converts all untagged pitches to be call untagged
  if (!is.null(filtered_df) && nrow(filtered_df) > 0 &&
      x_axis %in% names(filtered_df) &&
      y_axis %in% names(filtered_df)) {
    
    filtered_df$TagStatus <- ifelse(filtered_df[[tag]] == "Undefined" | is.na(filtered_df[[tag]]),
                                    "Untagged", as.character(filtered_df[[tag]]))
    #create plot
    plot <- ggplot(filtered_df, aes(x = .data[[x_axis]], y = .data[[y_axis]], color = TagStatus)) +
      geom_point(alpha = 0.7, size = 2) +
      #labels
      labs(
        x = map_with_label[[x_axis]],
        y = map_with_label[[y_axis]],
        title = paste(map_without_label[[y_axis]], "vs.", map_without_label[[x_axis]])) +
      theme_minimal() +
      #color coding the pitches
      scale_color_manual("Pitch Tag", values = c(
        "Fastball" = "red", 
        "Four-Seam" = "red",
        "Changeup" = "blue", 
        "ChangeUp" = "blue", 
        "Sinker" = "green", 
        "Curveball" = "brown", 
        "Slider" = "purple", 
        "Splitter" = "black", 
        "Cutter" = "pink",
        "Untagged" = "gray"
      )) +
      theme(
        plot.title = element_text(size = 9),           # Title text size
        axis.title = element_text(size = 7),
        axis.label = element_text(size = 6),
        legend.position = "none"
      )
  }
  return(plot)
}