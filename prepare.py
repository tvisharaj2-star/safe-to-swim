import pandas as pd
bacteria = pd.read_csv("bacteria.csv")
weather = pd.read_csv("weather.csv")
print(bacteria.columns)
print(weather.columns)

# Convert both date columns to real dates

bacteria["collect date"] = pd.to_datetime(bacteria["date"])
weather["time"] = pd.to_datetime(weather["time"])

#making table
weather = weather.sort_values("time")
weather["rain_1d"] = weather["precipitation"].shift(1)
weather["rain_3d"] = weather["precipitation"].shift(1).rolling(3). sum()
weather["rain_7d"] = weather["precipitation"].shift(1).rolling(7). sum()

#Merge — attach the weather to each beach bacteria test by matching dates
df = bacteria.merge(
    weather[["time", "rain_1d", "rain_3d", "rain_7d","temperature_2m_max "]],
    left_on="collect date",
    right_on="time",
    how="left")

print(df[["collect date", "rain_1d", "rain_3d", "rain_7d"]].head(10))

#combine file
df.to_excel("combine_data.xlsx", index=False)
