import streamlit as st
import pandas as pd
import folium
from geopy.geocoders import Nominatim
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import base64
import os
from collections import defaultdict
import random

# ------------------- App Logo -------------------
logo_path = os.path.join(os.path.dirname(__file__), "pureprofile_logo.png")
st.image(logo_path, width=200)


# ------------------- App Title -------------------
st.title("📍 Postcode Heatmap Generator")

# --- Custom Styling ---
st.markdown("""
    <style>
    /* Change primary button hover color */
    .stButton>button:hover {
        background-color: #269795 !important;
        color: white !important;
    }

    /* Optional: match primary color on active buttons */
    .stButton>button:focus {
        background-color: #269795 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)


# ------------------- Country Selection -------------------
country_options = {
    "Australia": "AU",
    "New Zealand": "NZ",
    "United States": "US"
}
selected_country_label = st.selectbox("Select the appropriate country first", list(country_options.keys()), index=0)
selected_country_code = country_options[selected_country_label]


# ------------------- Intensity Control -------------------
intensity = st.slider("Gradient Intensity", min_value=1, max_value=10, value=5)


# ------------------- File Upload -------------------
uploaded_file = st.file_uploader("Upload CSV or Excel file with Postcodes", type=["csv", "xlsx"])



# ------------------- Files for country -------------------
library_file = f"postcode_library_{selected_country_code}.csv"
missing_cache_file = f"missing_cache_{selected_country_code}.csv"

# ------------------- Load postcode libraries -------------------
@st.cache_data
def load_library(file_path):
    cache = defaultdict(list)
    if os.path.exists(file_path):
        df = pd.read_csv(file_path, dtype={"postcode": str})
        df["postcode"] = df["postcode"].str.strip()
        for _, row in df.iterrows():
            cache[row["postcode"]].append((row["lat"], row["lon"]))
    return cache

postcode_library = load_library(library_file)
missing_cache = load_library(missing_cache_file)

# ------------------- Geocoding -------------------
geolocator = Nominatim(user_agent="postcode_heatmap")

def normalize_postcode(postcode, country_code):
    postcode = str(postcode).strip()
    if country_code in ["AU", "NZ"]:
        return postcode.zfill(4)
    elif country_code == "US":
        return postcode.zfill(5)
    return postcode

def append_to_missing_cache(postcode, coords):
    new_row = pd.DataFrame([{
        "postcode": postcode,
        "lat": coords[0],
        "lon": coords[1]
    }])
    new_row.to_csv(missing_cache_file, mode='a', header=not os.path.exists(missing_cache_file), index=False)

def geocode_postcode(postcode):
    postcode = normalize_postcode(postcode, selected_country_code)
    fallback = postcode.lstrip("0")

    if "selected_coords" not in st.session_state:
        st.session_state.selected_coords = {}

    # Try postcode library
    if postcode in postcode_library:
        if postcode not in st.session_state.selected_coords:
            st.session_state.selected_coords[postcode] = random.choice(postcode_library[postcode])
        return st.session_state.selected_coords[postcode]
    elif fallback in postcode_library:
        if fallback not in st.session_state.selected_coords:
            st.session_state.selected_coords[fallback] = random.choice(postcode_library[fallback])
        return st.session_state.selected_coords[fallback]

    # Try missing cache
    if postcode in missing_cache:
        return random.choice(missing_cache[postcode])

    # Fallback: geocode using API
    try:
        print(f"postcode not found in library {postcode}")
        location = geolocator.geocode(f"{postcode}, {selected_country_label}")
        if location:
            coords = (location.latitude, location.longitude)
            append_to_missing_cache(postcode, coords)
            return coords
    except:
        pass
    return None

# ------------------- Main Heatmap Logic -------------------
if uploaded_file:
    # Read uploaded file
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
        st.error("❌ None of the postcodes could be geocoded. Please check your data.")
    else:
        df["latitude"] = df["latlon"].apply(lambda x: x[0])
        df["longitude"] = df["latlon"].apply(lambda x: x[1])
        st.success(f"✅ {len(df)} postcodes geocoded successfully.")

        # Prepare heatmap
        heat_data = [[row["latitude"], row["longitude"], intensity] for _, row in df.iterrows()]
        center = [df["latitude"].mean(), df["longitude"].mean()]

        m = folium.Map(location=center, zoom_start=5 if selected_country_code == "AU" else 6)
        HeatMap(heat_data, radius=15).add_to(m)

        # Display heatmap
        st.subheader("🗺️ Generated Heatmap")
        st_folium(m, width=700)

        # Export HTML map
        st.subheader("📤 Export Map as HTML")
        export_button = st.button("Download Heatmap")
        if export_button:
            map_html = m.get_root().render()
            b64 = base64.b64encode(map_html.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="heatmap_{selected_country_label}.html">Click here to download the HTML map</a>'
            st.markdown(href, unsafe_allow_html=True)
