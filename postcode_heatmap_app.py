import streamlit as st
import pandas as pd
import folium
from geopy.geocoders import Nominatim
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import base64
import os
from collections import defaultdict
import ast
import random

# --- Title ---
st.title("📍 Postcode Heatmap Generator")

# --- Upload ---
uploaded_file = st.file_uploader("Upload CSV or Excel file with Postcodes", type=["csv", "xlsx"])

# --- Country selection ---
country = st.selectbox(
    "Select country for postcode geocoding",
    ["Australia", "UK", "United States", "Canada", "New Zealand"],
    index=0  # Australia default
)

# --- Intensity control ---
intensity = st.slider("Gradient Intensity", min_value=1, max_value=10, value=5)

# --- Geocoder setup ---
geolocator = Nominatim(user_agent="postcode_heatmap")
cache_file = "geocode_cache.csv"


@st.cache_data
def load_postcode_cache():
    from collections import defaultdict
    cache = defaultdict(list)
    if os.path.exists(cache_file):
        cache_df = pd.read_csv(cache_file, dtype={"postcode": str})
        cache_df["postcode"] = cache_df["postcode"].str.strip()
        for _, row in cache_df.iterrows():
            cache[row["postcode"]].append((row["lat"], row["lon"]))
    return cache

geocode_cache = load_postcode_cache()


def save_geocode_cache():
    rows = []
    for pc, latlon_list in geocode_cache.items():
        for latlon in latlon_list:
            rows.append({"postcode": pc, "lat": latlon[0], "lon": latlon[1]})
    pd.DataFrame(rows).to_csv(cache_file, index=False)



def geocode_postcode(postcode):
    postcode = str(postcode).strip().zfill(4)
    fallback_postcode = postcode.lstrip("0")  # e.g., '0800' → '800'

    if "selected_coords" not in st.session_state:
        st.session_state.selected_coords = {}

    # Try full postcode first (e.g. 0800)
    if postcode in geocode_cache:
        if postcode not in st.session_state.selected_coords:
            st.session_state.selected_coords[postcode] = random.choice(geocode_cache[postcode])
        print(f"✅ Found in cache: {postcode}")
        return st.session_state.selected_coords[postcode]

    # Try fallback without leading zero (e.g. 800)
    elif fallback_postcode in geocode_cache:
        if fallback_postcode not in st.session_state.selected_coords:
            st.session_state.selected_coords[fallback_postcode] = random.choice(geocode_cache[fallback_postcode])
        print(f"✅ Found in cache (fallback): {fallback_postcode}")
        return st.session_state.selected_coords[fallback_postcode]
    try:
        location = geolocator.geocode(f"{postcode}, {country}")
        if location:
            latlon = (location.latitude, location.longitude)
            geocode_cache[postcode].append(latlon)  # Append to list
            save_geocode_cache()
            return latlon
    except:
        return None

# --- Main Logic ---
if uploaded_file:
    # Read data
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("Preview of Uploaded Data")
    st.write(df.head())

    postcode_column = st.selectbox("Select the column containing postcodes", df.columns)

    st.info("Geocoding postcodes (may take a few moments)...")

    df["latlon"] = df[postcode_column].apply(geocode_postcode)
    df = df.dropna(subset=["latlon"])

    if df.empty:
        st.error("❌ None of the postcodes could be geocoded. Please check the data or try a different country.")
    else:
        df["latitude"] = df["latlon"].apply(lambda x: x[0])
        df["longitude"] = df["latlon"].apply(lambda x: x[1])

        st.success(f"✅ {len(df)} postcodes geocoded successfully.")

        # Prepare heat data
        heat_data = [[row["latitude"], row["longitude"], intensity] for _, row in df.iterrows()]

        # Create map
        center = [df["latitude"].mean(), df["longitude"].mean()]
        m = folium.Map(location=center, zoom_start=5 if country == "Australia" else 6)
        HeatMap(heat_data, radius=15).add_to(m)

        # Display map
        st.subheader("🗺️ Generated Heatmap")
        st_folium(m, width=700)

        # Export map
        st.subheader("📤 Export Map as HTML")
        export_button = st.button("Download Heatmap")

        if export_button:
            map_html = m.get_root().render()
            b64 = base64.b64encode(map_html.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="heatmap_{country}.html">Click here to download the HTML map</a>'
            st.markdown(href, unsafe_allow_html=True)
