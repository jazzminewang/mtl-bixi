setwd("Path to Bixi Data")
library(plyr)

read_files <- function(x){
  data <- read.csv(x)
  data$Month <- substr(data$end_date,6,7) # Going with arrivals instead of departures
  data$Hour <- substr(data$end_date, 12,13)
  data$Day <- weekdays(as.Date(data$end_date))
  data$Year <- subsrt(data$end_date,1,4)
  data <- subset(data, is_member ==1)
  return(data)
}

files <- list.files()
data_s <- read_files(files[1])
for (i in 2:length(files))
  data_s <- rbind(data_s, read_files(files[i]))
save(data_s, file = "All_data.Rda")

setwd("Path to Weather Data")
read_w_files <- function(x){
  weather <- read.csv(x, skip = 16)
  weather <- weather[,c(1,7,25)]
  weather$Key <- substr(weather$Date.Time,1,13); weather$Date.Time <- NULL; names(weather) <- c("Temp", "Weather", "Key")
  return(weather)
}

files <- list.files()
weather <- read_w_files(files[1])
for(i in 2:length(files))
  weather <- rbind(weather, read_w_files(files[i]))

weather <- weather[order(weather$Key),]
weather <- subset(weather, substr(weather$Key,1,7) != "2017-06"); weather$Weather[1] <- "Mainly Clear"

library(zoo)
weather$Weather <- na.locf(weather$Weather)
weather$Weather <- gsub("Mostly", "", weather$Weather)
weather$Weather <- gsub("Mainly", "", weather$Weather)
weather$Weather <- gsub("Moderate Rain,Fog", "Moderate Rain", weather$Weather)

data_s$Key <- substr(data_s$end_date,1,13)
data_s2 <- ddply(data_s, as.quoted(c("end_station_code", "Year", "Month", "Hour", "Day", "Key")), summarize, sum_duration = sum(duration_sec), num_arrivals = length(end_station_code))
data_s2 <- merge(data_s2, weather, by = "Key", all.x = TRUE)


save(data_s2, file = "summarized_data_with_weather.Rda")

data_s2 <- subset(data_s2, end_station_code %in% c(6136, 6184, 6078, 6064, 6100,6154))

set.seed(1984)
data_s2 <- subset(data_s2, Month != 11)

data_s2$Weather <- gsub(" ", "", data_s2$Weather)
data_s2$Weather <- ifelse(nchar(data_s2$Weather)==0,NA, data_s2$Weather)
data_s2 <- data_s2[order(data_s2$Key),]
data_s2$Weather <- na.locf(data_s2$Weather)

data_s2 <- data_s2[sample(nrow(data_s2)),] 
split <- sample(nrow(data_s2), floor(nrow(data_s2) * 0.80))
training_data <- data_s2[split, ]
testing_data <- data_s2[-split, ] 


## Exploring the training set
library(magrittr)
library(ggplot2)
library(dplyr)
library(data.table)


training_data <- subset(training_data, substr(Key,1,10) != "2017-05-28") #remove any last sunday data from training

mod_glm <- glm(num_arrivals ~
                 as.factor(end_station_code) + as.factor(Year)+as.factor(Month)+Hour*Day+Temp+Weather,
               data = training_data,
               family = "poisson")

testing_data <- na.omit(testing_data)
testing_data$Predictions <- ceiling(exp(predict(mod_glm, newdata = testing_data)))
mean(abs(testing_data$Predictions - testing_data$num_arrivals))


# PRediction on last sunday data with graph
last_sunday <- subset(data_s2, substr(Key,1,10) == "2017-05-28")
last_sunday$Predictions <- ceiling(exp(predict(mod_glm, newdata = last_sunday)))
last_sunday <- last_sunday[,c("end_station_code", "Hour", "num_arrivals", "Predictions")]
last_sunday$Predictions <- ifelse(last_sunday$Predictions == last_sunday$num_arrivals, last_sunday$Predictions + 0.25, last_sunday$Predictions)
last_sunday <- melt(last_sunday, id = c("end_station_code","Hour"))

last_sunday %>%
  group_by(end_station_code,Hour, variable) %>%
  summarise(Arrivals = mean(value)) %>%
  ggplot(aes(x=Hour,y=Arrivals, color=variable, shape = variable))+
  geom_point()+
  facet_wrap(facets = ~ factor(end_station_code), ncol =3)+
  ggtitle("Prediction vs Actual Arrivals For Top 6 Stations on May 28, 2017")
