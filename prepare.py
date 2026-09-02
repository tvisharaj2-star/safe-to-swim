import pandas as pd

# Pull ALL rows from King County's API ($limit removes the 1000-row cap)
URL = "https://data.kingcounty.gov/resource/mbzm-4r9y.csv?$limit=50000"

try:
    beach = pd.read_csv(URL)
    print("Loaded from King County API")
    beach.to_csv("bacteria_backup.csv", index=False)   # save a fallback copy
except Exception as e:
    print("API failed, using backup file:", e)
    beach = pd.read_csv("bacteria_backup.csv")

# Normalize column names to lowercase (API uses Beach, Date, Geomean30d, etc.)
beach.columns = beach.columns.str.strip().str.lower()

print("Rows:", len(beach))
print("Beaches:", beach["beach"].nunique())
print(sorted(beach["beach"].unique()))

#Fixed the date and create the label!! 
beach["date"] = pd.to_datetime(beach["date"])
beach["unsafe"] = beach["hightoday"].astype(str).str.upper().eq("TRUE").astype(int)

print("Unsafe days:", beach["unsafe"].sum())

# My existing weather merge code:
weather = pd.read_csv(
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude=47.55&longitude=-122.20"
    "&start_date=2019-05-01&end_date=2026-08-31"
    "&daily=precipitation_sum,temperature_2m_max"
    "&timezone=America/Los_Angeles&format=csv",
    skiprows=3
)
weather.columns = weather.columns.str.strip().str.lower()
weather["time"] = pd.to_datetime(weather["time"])
weather = weather.sort_values("time")

# rainfall history columns
weather["rain_1d"] = weather["precipitation_sum (mm)"].shift(1)
weather["rain_3d"] = weather["precipitation_sum (mm)"].shift(1).rolling(3).sum()
weather["rain_7d"] = weather["precipitation_sum (mm)"].shift(1).rolling(7).sum()

# THE MERGE — this creates df
df = beach.merge(
    weather[["time", "rain_1d", "rain_3d", "rain_7d"]],
    left_on="date",
    right_on="time",
    how="left"
)

df.to_csv("combine_data.csv", index=False)
print("Saved:", len(df), "rows")
