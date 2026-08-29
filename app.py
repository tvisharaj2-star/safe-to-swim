import streamlit as st
import pandas as pd
import joblib
import requests
import datetime

# set_page_config MUST be the first streamlit command
st.set_page_config(page_title="Safe to Swim", page_icon="🏊", layout="centered")

# ---------- Lakes (defined BEFORE they're used) ----------
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

# ---------- Load model and data ----------
model = joblib.load("model.pkl")
data = pd.read_excel("combine_data.xlsx")
data.columns = data.columns.str.strip()
data["collect date"] = pd.to_datetime(data["collect date"])

# ---------- Weather function ----------
def get_rainfall(lat, lon, date):
    date = pd.to_datetime(date).date()
    today = datetime.date.today()
    start = date - datetime.timedelta(days=7)
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
    return r["daily"]["precipitation_sum"], r["daily"]["temperature_2m_max"]

# ---------- Page header ----------
st.title("🏊 Safe to Swim")
st.caption("Know before you go — is it safe to swim in King County today?")

# ---------- Map of all lakes ----------
map_data = pd.DataFrame([
    {"lat": info["lat"], "lon": info["lon"]}
    for info in LAKES.values()
])
st.map(map_data)

# ---------- Inputs ----------
lake = st.selectbox("Pick a lake", list(LAKES.keys()))
if lake:
    st.info(f"📍 You selected **{lake}**. Now choose a date below.")
picked_date = st.date_input("Pick a date")
check = st.button("Check this lake", type="primary")

if check:
    coords = LAKES[lake]

    # 1. Weather
    rain, temp = get_rainfall(coords["lat"], coords["lon"], picked_date)
    if rain is None:
        st.warning("Weather data isn't available for that date. Try a date within the next 2 weeks or in the past.")
        st.stop()

    rain_1d = rain[-2] if len(rain) >= 2 else 0
    rain_3d = sum(rain[-4:-1])
    rain_7d = sum(rain[:-1])
    watertempc = temp[-1]

    # 2. Bacteria history
    lake_rows = data[data["beach"] == lake].sort_values("collect date")
    if len(lake_rows) == 0:
        st.error(f"No historical data for {lake}.")
        st.stop()
    latest = lake_rows.iloc[-1]
    geomean30d = latest["geomean30d"]
    nsampleshigh30d = latest["nsampleshigh30d"]

    # 3. Model prediction
    features = pd.DataFrame([{
        "rain_1d": rain_1d, "rain_3d": rain_3d, "rain_7d": rain_7d,
        "watertempc": watertempc, "geomean30d": geomean30d,
        "nsampleshigh30d": nsampleshigh30d,
    }])
    prob = model.predict_proba(features)[0][1]

    # 4. Result
    avg_label = "low" if geomean30d < 50 else "elevated"
    temp_label = "warm" if watertempc > 20 else "cool"

    if prob > 0.30:
        st.error(f"⚠️ High risk at {lake} on {picked_date}")
        st.write(
            f"The water may not be safe for swimming today. "
            f"About {rain_3d:.0f} mm of rain fell over the last 3 days, "
            f"washing bacteria into the lake. "
            f"The water is also fairly {temp_label} at {watertempc:.0f}°C, "
            f"and warmer water lets bacteria grow faster. "
            f"The lake's 30-day bacteria average is {geomean30d:.0f} ({avg_label}), "
            f"with {nsampleshigh30d:.0f} high sample(s) recorded recently."
        )
    else:
        st.success(f"✅ Low risk at {lake} on {picked_date}")
        st.write(
            f"The water looks safe for swimming today. "
            f"Only about {rain_3d:.0f} mm of rain fell over the last 3 days, "
            f"so little bacteria has washed into the lake. "
            f"The water is {temp_label} at {watertempc:.0f}°C, which slows bacteria growth. "
            f"The lake's 30-day bacteria average is {geomean30d:.0f} ({avg_label}), "
            f"with {nsampleshigh30d:.0f} high sample(s) recorded recently."
        )

    # 5. Data to show if its safe to swim
    st.divider()
    if rain_3d > 15:
        rain3_level = "High 🔴"
    elif rain_3d > 5:
        rain3_level = "Medium 🟡"
    else:
        rain3_level = "Low 🟢"
    st.write(f"**Rain last 3 days:** {rain_3d:.1f} mm — {rain3_level}")

    if rain_7d > 30:
        rain7_level = "High 🔴"
    elif rain_7d > 10:
        rain7_level = "Medium 🟡"
    else:
        rain7_level = "Low 🟢"
    st.write(f"**Rain last 7 days:** {rain_7d:.1f} mm — {rain7_level}")

    if watertempc > 22:
        temp_level = "Warm 🔴"
    elif watertempc > 16:
        temp_level = "Mild 🟡"
    else:
        temp_level = "Cool 🟢"
    st.write(f"**Water temperature:** {watertempc:.1f} °C — {temp_level}")

    if geomean30d > 100:
        geo_level = "High 🔴"
    elif geomean30d > 50:
        geo_level = "Medium 🟡"
    else:
        geo_level = "Low 🟢"
    st.write(f"**30-day bacteria average:** {geomean30d:.0f} — {geo_level}")

    if nsampleshigh30d >= 3:
        high_level = "High 🔴"
    elif nsampleshigh30d >= 1:
        high_level = "Medium 🟡"
    else:
        high_level = "Low 🟢"
    st.write(f"**Recent high samples (30 days):** {nsampleshigh30d:.0f} — {high_level}")

    # 6. Plain-English rain note
    st.divider()
    if rain_3d > 11:
        st.info("🌧️ It rained recently — this can raise bacteria levels through runoff, which carries pet/farm waste, fertilizer, oil, and bacteria like E. coli into the lake.")
    elif 0 < rain_3d <= 11:
        st.info("☀️ Little recent rain — water is usually cleaner.")
    else:
        st.info("☀️ No recent rain — conditions suggest cleaner water.")

    st.caption("Bacteria values are from King County's most recent test; rain and temperature are live.")
    st.caption("Not affiliated with King County. Always check official advisories.")