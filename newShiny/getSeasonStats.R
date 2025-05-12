library(httr)
library(jsonlite)
library(dplyr)

#get all season stats for a player given playerid for specific seasonid
get_pitching_stats_only <- function(playerlinkid, seasonid = "34104") {
  apikey <- "vIpQsngDfc6Y7WVgAcTt"
  
  url <- paste0("https://api.pointstreak.com/baseball/player/stats/", playerlinkid, "/", seasonid, "/json")
  res <- GET(url, add_headers(apikey = apikey))
  if (status_code(res) != 200) return(NULL)
  
  json_data <- content(res, as = "text", encoding = "UTF-8")
  parsed <- fromJSON(json_data, simplifyDataFrame = FALSE)
  
  pitching_stats <- parsed$player$pitchingstats$season
  if (is.null(pitching_stats)) return(NULL)
  
  #return row and bind df
  df <- bind_rows(pitching_stats)
  return(df)
}
get_pitching_stats_only("1743144", "34104")
