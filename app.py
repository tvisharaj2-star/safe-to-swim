import streamlit as st
import pandas as pd
import joblib
import requests
import datetime
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Safe to Swim", page_icon="🏊", layout="centered")

# All the Lakes!
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

#  Load model and data 
model = joblib.load("model.pkl")
data = pd.read_excel("combine_data.xlsx")
data.columns = data.columns.str.strip()
data["collect date"] = pd.to_datetime(data["collect date"])

# Weather function
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

# ---------- Header ----------
st.title("🏊 Safe to Swim")
st.caption("Know before you go — is it safe to swim in King County today?")

# ---------- Tabs ----------
tab1, tab2 = st.tabs(["Check a date", "Trends & forecast"])

with tab1:
    # the clciker!!!
    m = folium.Map(location=[47.55, -122.20], zoom_start=10)
    for name, info in LAKES.items():
        folium.Marker(
            location=[info["lat"], info["lon"]],
            popup=name,
            tooltip=name,
            icon=folium.Icon(color="red")
        ).add_to(m)

    map_result = st_folium(m, height=300, width=700)

    
    if map_result and map_result.get("last_object_clicked_popup"):
        st.session_state["lake"] = map_result["last_object_clicked_popup"]

    lake_names = list(LAKES.keys())
    saved = st.session_state.get("lake", lake_names[0])
    default_index = lake_names.index(saved) if saved in lake_names else 0

    lake = st.selectbox("Pick a lake", lake_names, index=default_index)
    st.session_state["lake"] = lake      # keep it in sync

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

        # 2. Bacteria history (only records on or before the picked date)
        lake_rows = data[data["beach"] == lake].sort_values("collect date")
        if len(lake_rows) == 0:
            st.error(f"No historical data for {lake}.")
            st.stop()

        valid_rows = lake_rows[lake_rows["collect date"] <= pd.to_datetime(picked_date)]
        if len(valid_rows) == 0:
            st.error(f"No bacteria data available for {lake} before that date.")
            st.stop()

        latest = valid_rows.iloc[-1]
        data_date = latest["collect date"].date()
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

        if prob > 0.20:
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

        # 5. Factor breakdown
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

        # 6. extra info
        st.divider()
        if rain_3d > 11:
            st.info("🌧️ It rained recently — this can raise bacteria levels through runoff, which carries pet/farm waste, fertilizer, oil, and bacteria like E. coli into the lake.")
        elif 0 < rain_3d <= 11:
            st.info("☀️ Little recent rain — water is usually cleaner.")
        else:
            st.info("☀️ No recent rain — conditions suggest cleaner water.")

        st.caption(f"Bacteria values are from King County's test on {data_date}; rain and temperature are live.")
        st.caption("Not affiliated with King County. Always check official advisories.")

with tab2:
    lake = st.session_state.get("lake", list(LAKES.keys())[0])
    st.subheader(f"Past tests — {lake}")

    lake_rows = data[data["beach"] == lake].sort_values("collect date")
    if len(lake_rows) == 0:
        st.warning("No historical data for this lake.")
    else:
        recent = lake_rows.tail(10)
        chart_data = recent.set_index("collect date")[["geomean30d"]]
        st.line_chart(chart_data)
        st.caption("30-day bacteria geometric mean at each King County test date.")
        
    #7-day forcast
    
        # 7-day risk forecast
    st.divider()
    st.subheader("Next 7 days")
    st.caption("Predicted from the latest county test plus the weather forecast")

    coords = LAKES[lake]
    latest = lake_rows.iloc[-1]
    f_geomean = latest["geomean30d"]
    f_nhigh = latest["nsampleshigh30d"]
    f_date = latest["collect date"].date()

    cols = st.columns(7)
    for i in range(7):
        day = datetime.date.today() + datetime.timedelta(days=i)

        rain, temp = get_rainfall(coords["lat"], coords["lon"], day)
        if rain is None:
            continue

        f_rain_1d = rain[-2] if len(rain) >= 2 else 0
        f_rain_3d = sum(rain[-4:-1])
        f_rain_7d = sum(rain[:-1])
        f_temp = temp[-1]

        f_features = pd.DataFrame([{
            "rain_1d": f_rain_1d, "rain_3d": f_rain_3d, "rain_7d": f_rain_7d,
            "watertempc": f_temp, "geomean30d": f_geomean,
            "nsampleshigh30d": f_nhigh,
        }])
        f_prob = model.predict_proba(f_features)[0][1]

        with cols[i]:
            st.write(f"**{day.strftime('%a')}**")
            st.write("🔴" if f_prob > 0.20 else "🟢")
            st.write(f"{f_prob:.0%}")

    st.caption(
        f"Forecast uses King County's most recent test ({f_date}) with predicted "
        f"rainfall. Bacteria are not re-measured daily."
    )

    