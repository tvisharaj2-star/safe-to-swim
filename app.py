import streamlit as st
import pandas as pd
import joblib
import requests
import datetime

# ---------- Load model and data ----------
model = joblib.load("model.pkl")
data = pd.read_excel("combine_data.xlsx")
data.columns = data.columns.str.strip()
data["collect date"] = pd.to_datetime(data["collect date"])

# ---------- Lakes (real names from the data) + coordinates ----------
LAKES = {
    "Angle Lake":      {"lat": 47.42, "lon": -122.29},
    "Beaver Lake":     {"lat": 47.59, "lon": -122.02},
    "Echo Lake":       {"lat": 47.77, "lon": -122.34},
    "Enatai":          {"lat": 47.59, "lon": -122.19},
    "Fivemile Lake":   {"lat": 47.36, "lon": -122.30},
    "Gene Coulon":     {"lat": 47.50, "lon": -122.20},
    "Green Lake East": {"lat": 47.68, "lon": -122.32},
    "Green Lake West": {"lat": 47.68, "lon": -122.34},
}

# ---------- Get rainfall + temperature (past OR future) ----------
def get_rainfall(lat, lon, date):
    date = pd.to_datetime(date).date()
    today = datetime.date.today()
    start = date - datetime.timedelta(days=7)

    # future/today -> forecast service; past -> archive service
    if date >= today:
        base = "https://api.open-meteo.com/v1/forecast"
    else:
        base = "https://archive-api.open-meteo.com/v1/archive"

    url = (
        f"{base}"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start}&end_date={date}"
        "&daily=precipitation_sum,temperature_2m_max"
        "&timezone=America/Los_Angeles"
    )
    r = requests.get(url).json()
    if "daily" not in r:
        return None, None
    rain = r["daily"]["precipitation_sum"]
    temp = r["daily"]["temperature_2m_max"]
    return rain, temp

# ---------- Page ----------
st.set_page_config(page_title="Safe to Swim", page_icon="🏊", layout="centered")
st.title("🏊 Safe to Swim")
st.caption("Know before you go —")

lake = st.selectbox("Pick a lake", list(LAKES.keys()))
picked_date = st.date_input("Pick a date")

check = st.button("Check this lake", type="primary")

if check:
    coords = LAKES[lake]

    # 1. Weather for the picked date
    rain, temp = get_rainfall(coords["lat"], coords["lon"], picked_date)
    if rain is None:
        st.warning("Weather data isn't available for that date. Try a date within the next 2 weeks or in the past.")
        st.stop()

    rain_1d = rain[-2] if len(rain) >= 2 else 0
    rain_3d = sum(rain[-4:-1])
    rain_7d = sum(rain[:-1])
    watertempc = temp[-1]

    # 2. Most recent bacteria history for this lake
    lake_rows = data[data["beach"] == lake].sort_values("collect date")
    if len(lake_rows) == 0:
        st.error(f"No historical data for {lake}.")
        st.stop()
    latest = lake_rows.iloc[-1]
    geomean30d = latest["geomean30d"]
    nsampleshigh30d = latest["nsampleshigh30d"]

    # 3. Feed all six features to the model
    features = pd.DataFrame([{
        "rain_1d": rain_1d,
        "rain_3d": rain_3d,
        "rain_7d": rain_7d,
        "watertempc": watertempc,
        "geomean30d": geomean30d,
        "nsampleshigh30d": nsampleshigh30d,
    }])

    prob = model.predict_proba(features)[0][1]

    # 4. Result
    if prob > 0.30:
        st.markdown(f"# 🔴 High Risk")
        st.markdown(f"### {lake} — {picked_date}")
        st.error("Recent rain suggests bacteria may be high. Best to stay out.")
    else:
        st.markdown(f"# 🟢 Safe to Swim")
        st.markdown(f"### {lake} — {picked_date}")
        st.success("Conditions look good. Always check official advisories too.")

    # 5. Show the numbers behind it
    st.divider()
    st.metric("Rain in last 3 days", f"{rain_3d:.1f} mm")
    st.metric("Rain in last 7 days", f"{rain_7d:.1f} mm")
    st.caption("Not affiliated with King County. Always check official advisories.")

    st.divider()
    if rain_3d > 11:
        st.info(f"🌧️ It rained recently — this can raise bacteria levels due to runoffs. Components included in runoffs include: farm/pet waste, fertilizer, oil, dirt, and bacterias that include E.coli")
    else:
        st.info("☀️ Little recent rain — water is usually cleaner.")

    with st.expander("How does this work?"):
        st.write(
        "This app uses King County bacteria test results. It combines each lake's most "
        "recent tests with the live weather forecast to predict risk on days "
        "the county hasn't tested — including future dates."
    )