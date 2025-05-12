library(shiny)
library(httr)
library(jsonlite)
library(DT)
library(rsconnect)
library(ggplot2)
library(tidyr)
library(shinyjs)


# source files
source("getPointstreakPlayers.R")
source("getALPBdata.R")
source("getSeasonStats.R") 
source("getALPBpitches.R") 

# ui card helper
card_w_header <- function(title, body) {
  div(class = "card",
      div(class = "card-header bg-info text-white text-center font-weight-bold",
          style = "padding-top: 5px; padding-bottom: 5px;",
          title),
      div(class = "card-body d-flex justify-content-center align-items-center",
          div(style = "text-align: center; width: 100%;", body)
      )
  )
}

# dropdown
pitchers_df <- pitchers_df %>%
  mutate(full_name = paste(fname, lname))

print(colnames(pitchers_df))

# shiny ui

ui <- fluidPage(
  
  useShinyjs(),
  
  tags$head(
    tags$style(HTML("
      #page-spinner {
        display: none;
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        z-index: 9999;
      }
    "))
  ),
  
  div(id = "page-spinner", 
      div(style = "text-align: center; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.3);",
          h3("Generating PDF... This may take some time"),
          tags$div(class = "spinner-border text-info", role = "status", style = "width: 3rem; height: 3rem;")
      )
  ),
  
  
  fluidRow(
    column(1),
    column(10,
           div(style = "text-align: center;", h1("ALPB Pitchers")),
           
           #first row
           #pitcher dropdown
           fluidRow(
             
             column(4,
                    wellPanel(selectInput("selected_player", "Choose a Pitcher:", choices = pitchers_df$full_name))
             ),
             
             #download pdf btn
             column(6,
                    
             ),
             column(2,
                    downloadButton("download_pdf", "Download PDF")
             )
             
           ),
           
           #second row
           fluidRow(
             column(4,
                    div(style = "margin-bottom: 20px",
                        card_w_header("Pitcher Information",
                                      div(style = "text-align: left; margin-top: 2vh;",
                                          fluidRow(
                                            column(6, uiOutput("player_photo")),
                                            
                                            column(6, uiOutput("player_info_placeholder"))
                                          )
                                      )
                        )
                    )
             ),
             column(8,
                    card_w_header("Season Stats", tableOutput("season_stats_output"))
             )
           ),
           #third row
           fluidRow(
             id = "alpbRow3",
             #vel plot
             column(6,
                    card_w_header(uiOutput("scatter_header"), plotOutput("velPlot", height = "300px"))
             ),
             
             #break graph
             column(6,
                    card_w_header("Induced Vertical Break vs Horizontal Break", plotOutput("breakPlot", height = "300px"))
             )
           ),
           #4th row -- buttons
           fluidRow(
             id = "alpbRow4",
             column(3,
                    radioButtons("break_type", "Break Type:",
                                 choices = c("Vertical Break" = "induced_vert_break",
                                             "Horizontal Break" = "horz_break")),
                    
                    
             ), column(3,  radioButtons("tag_choice", "Pitch Tagging Method:",
                                        choices = c("Machine Tagged" = "auto_pitch_type",
                                                    "Human Tagged" = "tagged_pitch_type")
             )
             ),
             column(3,
                    uiOutput("pitch_type_ui")
             )
           ),
           #5th row - heat maps
           fluidRow(
             id = "alpbRow5",
             column(6,
                    card_w_header("Pitch map vs RH Batters", plotOutput("heatmap_right", height = "300px"))
             ),
             
             column(6,
                    card_w_header("Pitch map vs LH Batters", plotOutput("heatmap_left", height = "300px"))
             )
           ),
           
           #6th row -- pitch type 
           fluidRow(
             id = "alpbRow6",
             column(12,
                    card_w_header("Pitch Type Percentages for Each Count",DTOutput("pitchTable"))
             ))
    ),
    column(1)
  )
)

# server
server <- function(input, output, session) {
  shinyjs::onclick("download_pdf", {
    runjs("document.getElementById('page-spinner').style.display = 'block';")
  })
  
  
  observe({
    if (is.null(alpb_player_id())) {
      shinyjs::hide("alpbRow3")
      shinyjs::hide("alpbRow4")
      shinyjs::hide("alpbRow5")
      shinyjs::hide("alpbRow6")
    } else {
      shinyjs::show("alpbRow3")
      shinyjs::show("alpbRow4")
      shinyjs::show("alpbRow5")
      shinyjs::show("alpbRow6")
    }
  })
  
  
  # Pointstreak player row
  selected_player_row <- reactive({
    pitchers_df %>%
      filter(full_name == input$selected_player)
  })
  
  # ALPB player ID
  alpb_player_id <- reactive({
    selected <- selected_player_row()
    result <- get_alpb_pitcher_info(selected$fname, selected$lname)
    
    if (is.null(result) || is.na(result$player_id) || result$player_id == "data unavailable") {
      return(NULL)
    } else {
      return(result$player_id)
    }
  }) %>% 
    bindCache(input$selected_player)
  
  #ALPB pitch data
  pitch_data <- reactive({
    get_alpb_pitches_by_pitcher(alpb_player_id())
  }) %>%
    bindCache(alpb_player_id())
  
  #Header for the scatter plot
  output$scatter_header <- renderUI({
    if(input$break_type == "induced_vert_break") {
      tagList("Vertical Break vs Velocity")  
    } else if(input$break_type == "horz_break") {
      tagList("Horizontal Break vs Velocity")  
    }
  })
  
  selected_pitcher <- reactive({
    input$selected_player  # Return the full name of the selected pitcher
  })
  
  #generates a list of unique pitches in a pitcher's repertoire based on tag
  pitch_types <- reactive({
    data <- pitch_data()
    req(data)
    if (input$tag_choice == "auto_pitch_type") {
      pitch_types <- unique(na.omit(data$auto_pitch_type))
    } else {
      pitch_types <- unique(na.omit(data$tagged_pitch_type))
    }
    pitch_types <- pitch_types[pitch_types != "Undefined"]
  }) %>%
    bindCache(pitch_data(), input$tag_choice)
  
  
  output$pitch_type_ui <- renderUI({
    req(pitch_types())
    selectInput("selected_pitch_type", "Select Pitch Type:",
                choices = c("All", pitch_types()), selected = "All")
  })
  
  output$player_info_placeholder <- renderUI({
    req(selected_player_row())  # Ensure there's a selection
    player <- selected_player_row()
    
    tagList(
      div(HTML(paste0("<b>Name:</b> ", player$full_name))),
      div(HTML(paste0("<b>Team:</b> ", player$teamname))),
      div(HTML(paste0("<b>Player ID:</b> ", player$playerid))),
      div(HTML(paste0("<b>Hometown:</b> ", player$hometown))),
      div(HTML(paste0("<b>Throws:</b> ", player$throws))),
      div(HTML(paste0("<b>Weight:</b> ", player$weight))),
      div(HTML(paste0("<b>Height:</b> ", player$height))),
      div(HTML(paste0("<b>Bats:</b> ", player$bats))),
      # div(HTML(paste0("<b>Photo:</b> ", player$photo)))
    )
  })
  
  
  
  
  source('getGraphs.R')
  
  #break vs velocity plot
  output$velPlot <- renderPlot({
    data <- pitch_data()
    shiny::validate(shiny::need(!is.null(data) && nrow(data) > 0, "Need data"))
    build_graph(data, "rel_speed", input$break_type, input$tag_choice)
  }) %>%
    bindCache(pitch_data(), input$break_type, input$tag_choice)
  
  #vert break vs horz break plot
  output$breakPlot <- renderPlot({
    build_graph(pitch_data(), "horz_break", "induced_vert_break", input$tag_choice)
  }) %>%
    bindCache(pitch_data(), input$tag_choice)
  
  source('getHeatMap.R')
  #Creates heatmap vs RHB according to current pitch filter
  output$heatmap_right <- renderPlot({
    data <- pitch_data()
    req(data)
    #filters for RHB
    filtered_data <- data[data$batter_side == "Right", ]
    #filters for current pitch type
    if (!is.null(input$selected_pitch_type) && input$tag_choice == "auto_pitch_type" && input$selected_pitch_type != "All") {
      filtered_data <- filtered_data[filtered_data$auto_pitch_type == input$selected_pitch_type, ]
    } else if (!is.null(input$selected_pitch_type) && input$tag_choice == "tagged_pitch_type" && input$selected_pitch_type != "All") {
      filtered_data <- filtered_data[filtered_data$tagged_pitch_type == input$selected_pitch_type, ]
    }
    build_heatmap(filtered_data)
  }) %>%
    bindCache(pitch_data(), input$selected_pitch_type, input$tag_choice)
  
  #Creates heatmap vs LHB according to current pitch filter
  output$heatmap_left <- renderPlot({
    data <- pitch_data()
    req(data)
    #filters for LHB
    filtered_data <- data[data$batter_side == "Left", ]
    #filters for current pitch type
    if (!is.null(input$selected_pitch_type) && input$tag_choice == "auto_pitch_type" && input$selected_pitch_type != "All") {
      filtered_data <- filtered_data[filtered_data$auto_pitch_type == input$selected_pitch_type, ]
    } else if (!is.null(input$selected_pitch_type) && input$tag_choice == "tagged_pitch_type" && input$selected_pitch_type != "All") {
      filtered_data <- filtered_data[filtered_data$tagged_pitch_type == input$selected_pitch_type, ]
    }
    build_heatmap(filtered_data)
  }) %>%
    bindCache(pitch_data(), input$selected_pitch_type, input$tag_choice)
  
  
  source('getPDFReport.R')
  output$download_pdf <- downloadHandler(
    filename = function() {
      paste0(selected_pitcher(), " Pitcher Report.pdf")
    },
    content = function(file) {
      #might be a little slow so we show a message
      session$sendCustomMessage("hideSpinner", TRUE)
      pdf_path <- NULL
      stats <- get_pitching_stats_only(selected_player_row()$playerlinkid)
      #creates PDF based on what data is available
      if ((is.null(stats) || nrow(stats) == 0) && is.null(alpb_player_id())) {
        pdf_path <- get_no_data_pdf(selected_pitcher())
      }
      else if (is.null(alpb_player_id())){
        pdf_path<- get_no_ALPB_pdf(selected_player_row()$playerlinkid, selected_pitcher())
      }
      else if (is.null(stats) || nrow(stats) == 0){
        pdf_path<- get_no_poinstreak_pdf(pitch_data(), selected_pitcher(), input$tag_choice)
      }
      else {
        pdf_path <- get_all_pdf(selected_player_row()$playerlinkid, pitch_data(), selected_pitcher(), input$tag_choice)
      }

      # Copy it to the file path that downloadHandler expects
      file.copy(pdf_path, file)
      shinyjs::runjs("document.getElementById('page-spinner').style.display = 'none';")
      
    },
    contentType = "application/pdf"
  )
  
  source("pitchSplit.R")
  
  # Render the pitch split data table
  output$pitchTable <- renderDT({
    req(pitch_data())
    df <- get_pitch_type_percentages(pitch_data(), input$tag_choice)
    datatable(df, options = list(pageLength = 12, scrollX = TRUE))  # Display the table
  })
  
  
  
  # Show full player info
  output$player_info <- renderTable({
    req(selected_player_row())
    selected_player_row() %>% dplyr::select(-full_name)
  })
  
  #season stats from getSeasonStats.R
  output$season_stats_output <- renderTable({
    req(selected_player_row())
    playerlinkid <- selected_player_row()$playerlinkid
    stats <- get_pitching_stats_only(playerlinkid)
    
    if (is.null(stats)) {
      return(tibble::tibble(message = "No season stats found for this player."))
    }
    
    stats
  })
  
  output$player_photo <- renderUI({
    req(selected_player_row())
    img_url <- selected_player_row()$photo
    
    if (!is.na(img_url) && nzchar(img_url)) {
      tags$img(src = img_url, width = "100%", style = "border-radius: 8px;")
    } else {
      tags$p("⚠️ No photo available.")
    }
  })
  
  
}

shinyApp(ui = ui, server = server)