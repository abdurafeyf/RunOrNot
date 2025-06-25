import streamlit as st
import requests
from datetime import datetime
from dateutil import parser
import pytz
import matplotlib.pyplot as plt

st.set_page_config(page_title="Running Weather Advisor", layout="centered")
st.title("🏃 Running Weather Advisor")

# Auto-locate user IP
st.subheader("📍 Location Detection")
with st.spinner("Detecting your location via IP..."):
    ipinfo = requests.get("https://ipinfo.io/json").json()
    loc = ipinfo["loc"].split(",")
    lat = float(loc[0])
    lon = float(loc[1])
    city = ipinfo.get("city", "Unknown")
    st.success(f"Detected Location: {city} ({lat}, {lon})")

if st.button("Check Running Conditions"):
    # Fetch weather data
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m",
        "current_weather": True,
        "timezone": "auto"
    }
    res = requests.get(url, params=params)
    if res.status_code == 200:
        data = res.json()
        temp = data["current_weather"]["temperature"]

        # Match closest hour
        current_time = parser.parse(data["current_weather"]["time"])
        times = [parser.parse(t) for t in data["hourly"]["time"]]
        closest_idx = min(range(len(times)), key=lambda i: abs(times[i] - current_time))
        humidity = data["hourly"]["relative_humidity_2m"][closest_idx]

        # Heat Index Formula
        def compute_heat_index(T, RH):
            if T < 27:
                return T
            HI = (-8.78 + 1.611*T + 2.339*RH - 0.146*T*RH
                  - 0.0123*T*T - 0.0164*RH*RH + 0.00221*T*T*RH
                  + 0.000725*T*RH*RH - 0.00000358*T*T*RH*RH)
            return round(HI, 1)

        heat_index = compute_heat_index(temp, humidity)

        # Risk Classification + Pace Adjustment
        def risk_level(hi):
            if hi < 30:
                return ("✅ Good", "Ideal for running. Stay hydrated.", "No change")
            elif hi < 35:
                return ("⚠️ Moderate", "Run slower, hydrate more.", "Reduce pace by 5–10%")
            elif hi < 40:
                return ("❌ Risky", "Consider running early or indoors.", "Reduce pace by 15–20%")
            else:
                return ("🛑 Dangerous", "Avoid running outside.", "Avoid running")

        level, advice, pace_tip = risk_level(heat_index)

        # Show Metrics
        st.metric("Temperature", f"{temp} °C")
        st.metric("Humidity", f"{humidity} %")
        st.metric("Feels Like (Heat Index)", f"{heat_index} °C")
        st.subheader(f"Condition: {level}")
        st.info(advice)
        st.warning(f"🏃 Pace Adjustment: {pace_tip}")

        # Plot hourly forecast
        st.subheader("📊 Next 24h Running Outlook")
        future_times = times[closest_idx:closest_idx+24]
        future_temp = data["hourly"]["temperature_2m"][closest_idx:closest_idx+24]
        future_humid = data["hourly"]["relative_humidity_2m"][closest_idx:closest_idx+24]
        future_hi = [compute_heat_index(t, h) for t, h in zip(future_temp, future_humid)]

        labels = [t.strftime("%H:%M") for t in future_times]
        fig, ax = plt.subplots()
        ax.plot(labels, future_hi, label="Heat Index (°C)", color="tomato")
        ax.set_ylabel("Heat Index (°C)")
        ax.set_xlabel("Time")
        ax.set_xticks(labels[::3])
        ax.set_title("Forecast Heat Index (Next 24h)")
        ax.grid(True)
        ax.legend()
        st.pyplot(fig)

    else:
        st.error("Failed to fetch weather. Try again later.")
