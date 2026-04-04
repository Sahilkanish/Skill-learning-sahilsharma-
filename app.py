import streamlit as st
from ultralytics import YOLO
from PIL import Image
import sqlite3
import pandas as pd
from datetime import datetime
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval
import os

# --- Database setup ---
DB_NAME = 'road_reports_v2.db'

def setup_db():
    conn = sqlite3.connect(DB_NAME)
    curr = conn.cursor()
    curr.execute('''CREATE TABLE IF NOT EXISTS road_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp TEXT, 
                  lat REAL, 
                  lon REAL, 
                  potholes INTEGER,
                  cracks INTEGER)''')
    conn.commit()
    conn.close()

def save_data(lat, lon, p_count, c_count):
    conn = sqlite3.connect(DB_NAME)
    curr = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curr.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks) VALUES (?, ?, ?, ?, ?)", 
                 (now, lat, lon, p_count, c_count))
    conn.commit()
    conn.close()
    st.success("✅ Report saved to Database!")

setup_db()

# --- UI Config ---
st.set_page_config(page_title="AI Road Inspector", layout="centered")
st.title("🛣️AI ROAD DAMAGE DETECTOR🛣️")

if 'detection_done' not in st.session_state:
    st.session_state.detection_done = False

# --- SIDEBAR ---
st.sidebar.header("Control Panel")

# 1. Image Upload

uploaded_file = st.sidebar.file_uploader("📷 Step 1: Upload Image📷", type=['jpg', 'jpeg', 'png'])

# 2. Location Settings

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Step 2: Location 📍")
if st.sidebar.button("Get My Live Location"):
    loc = streamlit_js_eval(data_of='getCurrentPosition', key='get_loc')
    if loc:
        st.session_state.auto_lat = loc['coords']['latitude']
        st.session_state.auto_lon = loc['coords']['longitude']

u_lat = st.sidebar.number_input("Latitude", value=st.session_state.get('auto_lat', 28.6139), format="%.6f")
u_lon = st.sidebar.number_input("Longitude", value=st.session_state.get('auto_lon', 77.2090), format="%.6f")

# 3. Model Selection

st.sidebar.markdown("---")
st.sidebar.markdown(" Ⓜ️ Step 3: Model Ⓜ️")
st.sidebar.info("Model: Standard Pothole Detector")

# 4. Database Section
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Step 4: Database 📊")
report_filter = st.sidebar.selectbox("History Filter", ["All Reports", "Potholes Only", "Cracks Only"])
show_db = st.sidebar.button("📊 View/Refresh Database")

# --- MODEL PATH SECTION ---
def load_yolo():
    path = 'best.pt'
    return YOLO(path) if os.path.exists(path) else None

yolo_model = load_yolo()

# --- MAIN PAGE LOGIC ---
if uploaded_file:
    img = Image.open(uploaded_file)
    
    if st.button("🚀 Run AI Detection", type="primary", use_container_width=True):
        if yolo_model:
            results = yolo_model.predict(img, conf=0.15, iou=0.45)
            st.session_state.res_img = results[0].plot()
            
            labels = results[0].boxes.cls.tolist()
            st.session_state.p_count = labels.count(0) # 0 for pothole
            st.session_state.c_count = labels.count(1) # 1 for crack
            
            st.session_state.last_lat = u_lat
            st.session_state.last_lon = u_lon
            st.session_state.detection_done = True
        else:
            st.error("Model file not found!")

    if st.session_state.detection_done:
        st.markdown("---")
        st.image(st.session_state.res_img, use_container_width=True)

        p, c = st.session_state.p_count, st.session_state.c_count
        
        if p > 3:
            st.error(f"🚨 **STATUS: ROAD DAMAGED** ({p} Potholes found)")
        elif p > 0:
            st.warning(f"⚠️ **STATUS: NEEDS REPAIR** ({p} Potholes found)")
        else:
            st.success("✅ **STATUS: ROAD PERFECT**")

        if st.button("💾 Save Report to Database", use_container_width=True):
            save_data(st.session_state.last_lat, st.session_state.last_lon, p, c)

        # --- GRAPH SECTION ---
        
        st.markdown(" 📈 Detection Analysis")
        c1, c2 = st.columns(2)
        
        with c1:
            st.write("**Damage Distribution**")
            chart_data = pd.DataFrame({'Count': [p, c]}, index=['Potholes', 'Cracks'])
            st.bar_chart(chart_data)
            
        with c2:
            st.write("**Data Summary**")
            st.table(pd.DataFrame({
                "Parameter": ["Latitude", "Longitude", "Potholes Found", "Cracks Found"], 
                "Value": [f"{st.session_state.last_lat:.4f}", f"{st.session_state.last_lon:.4f}", p, c]
            }))

        # --- MAP & LOCATION SECTION  ---
        st.markdown(" 🗺️ Damage Location Map")
        m = folium.Map(location=[st.session_state.last_lat, st.session_state.last_lon], zoom_start=16)
        folium.Marker(
            [st.session_state.last_lat, st.session_state.last_lon], 
            popup=f"Potholes: {p}, Cracks: {c}",
            icon=folium.Icon(color='red' if p > 0 else 'green')
        ).add_to(m)
        st_folium(m, width=700, height=300)

# --- SHOW DATABASE ---
if show_db:
    st.markdown("---")
    st.subheader("📊 Saved Reports History")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM road_logs ORDER BY id DESC", conn)
    conn.close()
    
    if not df.empty:
        if report_filter == "Potholes Only":
            df = df[df['potholes'] > 0]
        elif report_filter == "Cracks Only":
            df = df[df['cracks'] > 0]
            
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Filtered Report", data=csv, file_name="road_report.csv", mime="text/csv")
    else:
        st.info("No records found in database.")
