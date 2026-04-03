import streamlit as st
from ultralytics import YOLO
from PIL import Image
import os
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap

# 1. Page Config
st.set_page_config(page_title="Road Damage Detector", layout="wide")
st.title("🛣️ Road Damage Detection System")

# 2. Model Load
model_path = r'C:\Users\sahil\Downloads\archive\data\runs\detect\train7\weights\best.pt'
model = YOLO('best.pt') 

# 3. Session State Initialization (Results ko hold karne ke liye)
if 'history' not in st.session_state:
    st.session_state.history = []
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

# 4. Sidebar
st.sidebar.header("Upload & Location")
img_file = st.sidebar.file_uploader("Upload Road Image", type=['jpg', 'jpeg', 'png'], key="road_uploader")

st.sidebar.subheader("Set Location")
lat = st.sidebar.number_input("Latitude", value=28.6139, format="%.6f")
lon = st.sidebar.number_input("Longitude", value=77.2090, format="%.6f")

graph_path = r'C:\Users\sahil\Downloads\archive\data\runs\detect\train7\results.png'

# 5. Prediction Logic
if img_file is not None:
    # "Analyze Road" dabane par result session_state mein save hoga
    if st.sidebar.button("Analyze Road"):
        image = Image.open(img_file)
        results = model(image)
        res_plotted = results[0].plot() 
        count = len(results[0].boxes)

        # Result ko memory mein save kar rahe hain
        st.session_state.last_result = {
            'image': res_plotted,
            'count': count
        }
        
        # History update for map
        st.session_state.history.append({'lat': lat, 'lon': lon, 'count': count})

# 6. Display Results (Agar memory mein data hai to dikhao)
if st.session_state.last_result is not None:
    res = st.session_state.last_result
    
    if res['count'] == 0:
        st.success(f"✅ Road is Perfect (0 Potholes)")
    elif 1 <= res['count'] <= 2:
        st.warning(f"⚠️ Road Repair Par Hai (Total Potholes: {res['count']})")
    else:
        st.error(f"🚨 Road Damaged Hai! (Total Potholes: {res['count']})")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Live Detection")
        st.image(res['image'], channels="BGR", use_container_width=True)
    with col2:
        st.subheader("Training Analysis Graph")
        if os.path.exists(graph_path):
            st.image(graph_path, use_container_width=True)

# 7. Map Section (Hamesha visible rahega ya history hone par dikhega)
st.divider()
st.subheader("🗺️ Road Damage Heatmap")

if st.session_state.history:
    m = folium.Map(location=[lat, lon], zoom_start=12)
    heat_data = [[h['lat'], h['lon'], h['count']] for h in st.session_state.history if h['count'] > 0]
    
    if heat_data:
        HeatMap(heat_data).add_to(m)
    
    for h in st.session_state.history:
        folium.Marker(
            [h['lat'], h['lon']], 
            popup=f"Potholes: {h['count']}",
            icon=folium.Icon(color="red" if h['count'] > 2 else "orange")
        ).add_to(m)

    st_folium(m, width=1200, height=500, key="main_map")
else:
    st.info("Photo analyze karein taaki map par data dikh sake.")
