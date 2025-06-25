import streamlit as st
import requests
from datetime import datetime, timedelta
from dateutil import parser
import matplotlib.pyplot as plt
import pytz

st.set_page_config(page_title="Running Weather Advisor", layout="centered")
st.title("🏃 Running Weather Advisor")

# --- Location Detection ---
st.subheader("📍 Location Detection")
city_name = st.text_input("Enter City (or leave blank to auto-detect via IP)", "")

if city_name:
    # Use OpenCage or Nominatim for geocoding (this uses Open-Meteo built-in geocoding)
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1"
    geo_res = requests.get(geo_url).json()
    if "results" in geo_res and len(geo_res["results"]) > 0:
        lat = geo_res["results"][0]["latitude"]
        lon = geo_res["results"][0]["longitude"]
        city = geo_res["results"][0]["name"]
        st.success(f"City found: {city} ({lat}, {lon})")
    else:
        st.error("City not found.")
        st.stop()
else:
    ipinfo = requests.get("https://ipinfo.io/json").json()
    loc = ipinfo["loc"].split(",")
    lat = float(loc[0])
    lon = float(loc[1])
    city = ipinfo.get("city", "Unknown")
    st.success(f"Auto-detected Location: {city} ({lat}, {lon})")

if st.button("Check Running Conditions"):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,weathercode",
        "current_weather": True,
        "timezone": "auto"
    }
    res = requests.get(url, params=params)

    aqi_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&hourly=pm10,pm2_5&timezone=auto"
    aqi_res = requests.get(aqi_url).json()

    if res.status_code == 200:
        data = res.json()
        times = [parser.parse(t) for t in data["hourly"]["time"]]
        temp_series = data["hourly"]["temperature_2m"]
        humid_series = data["hourly"]["relative_humidity_2m"]
        wcode_series = data["hourly"]["weathercode"]

        def compute_heat_index(T, RH):
            if T < 27:
                return T
            HI = (-8.78 + 1.611*T + 2.339*RH - 0.146*T*RH
                  - 0.0123*T*T - 0.0164*RH*RH + 0.00221*T*T*RH
                  + 0.000725*T*RH*RH - 0.00000358*T*T*RH*RH)
            return round(HI, 1)

        # --- Current weather ---
        now = parser.parse(data["current_weather"]["time"])
        closest_idx = min(range(len(times)), key=lambda i: abs(times[i] - now))
        current_temp = temp_series[closest_idx]
        current_humid = humid_series[closest_idx]
        heat_index = compute_heat_index(current_temp, current_humid)

        def risk_level(hi):
            if hi < 30:
                return ("✅ Good", "Ideal for running. Stay hydrated.", "No gear needed")
            elif hi < 35:
                return ("⚠️ Moderate", "Run slower, hydrate more.", "Bring water")
            elif hi < 40:
                return ("❌ Risky", "Consider running early or indoors.", "Wear light, reflective clothing")
            else:
                return ("🛑 Dangerous", "Avoid running outside.", "Stay indoors")

        level, advice, gear = risk_level(heat_index)

        st.metric("Temperature", f"{current_temp} °C")
        st.metric("Humidity", f"{current_humid} %")
        st.metric("Feels Like (Heat Index)", f"{heat_index} °C")
        st.subheader(f"Condition: {level}")
        st.info(advice)
        st.warning(f"🎒 Gear Suggestion: {gear}")

        # --- AQI ---
        if "hourly" in aqi_res:
            pm2_5 = aqi_res["hourly"]["pm2_5"][closest_idx]
            pm10 = aqi_res["hourly"]["pm10"][closest_idx]
            st.subheader("🌫️ Air Quality")
            st.metric("PM2.5", f"{pm2_5:.1f} µg/m³")
            st.metric("PM10", f"{pm10:.1f} µg/m³")
            if pm2_5 > 35 or pm10 > 50:
                st.error("Air quality is poor. Consider running indoors.")
            else:
                st.success("Air quality is acceptable for running.")

        # --- Best Time to Run Today ---
        st.subheader("🕒 Best Time to Run Today")
        today = now.date()
        safe_times = []
        for i, t in enumerate(times):
            if t.date() == today:
                hi = compute_heat_index(temp_series[i], humid_series[i])
                if hi < 33:
                    safe_times.append(t)

        if safe_times:
            windows = []
            start = safe_times[0]
            for i in range(1, len(safe_times)):
                if (safe_times[i] - safe_times[i-1]) > timedelta(hours=1):
                    windows.append((start, safe_times[i-1]))
                    start = safe_times[i]
            windows.append((start, safe_times[-1]))

            best = max(windows, key=lambda w: (w[1] - w[0]).seconds)
            st.success(f"Best Window: {best[0].strftime('%H:%M')}–{best[1].strftime('%H:%M')}")
        else:
            st.warning("No optimal time found today. Try early morning tomorrow.")

        # --- 3-Day Planner ---
        st.subheader("📅 3-Day Running Planner")
        planner = {}
        for i, t in enumerate(times):
            hi = compute_heat_index(temp_series[i], humid_series[i])
            if hi < 33:
                d = t.strftime("%Y-%m-%d")
                if d not in planner:
                    planner[d] = []
                planner[d].append(t.strftime("%H:%M"))

        for day, slots in planner.items():
            if slots:
                st.success(f"{day}: {slots[0]}–{slots[-1]}")
            else:
                st.warning(f"{day}: No safe running time")

        # --- Heat Index Forecast Chart ---
        st.subheader("📈 Heat Index Forecast")
        next_24h = times[closest_idx:closest_idx+24]
        next_hi = [compute_heat_index(temp_series[i], humid_series[i]) for i in range(closest_idx, closest_idx+24)]
        fig, ax = plt.subplots()
        ax.plot([t.strftime("%H:%M") for t in next_24h], next_hi, label="Heat Index", color="tomato")
        ax.set_xlabel("Hour")
        ax.set_ylabel("Heat Index (°C)")
        ax.set_title("Next 24h Heat Index")
        ax.grid(True)
        ax.legend()
        st.pyplot(fig)

    else:
        st.error("Failed to fetch weather data.")
