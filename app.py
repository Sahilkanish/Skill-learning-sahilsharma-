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

# --- 1. DATABASE SETUP ---
DB_NAME = 'road_reports_v2.db'

def setup_db():
    conn = sqlite3.connect(DB_NAME)
    curr = conn.cursor()
    curr.execute('''CREATE TABLE IF NOT EXISTS road_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, lat REAL, lon REAL, potholes INTEGER, cracks INTEGER)''')
    curr.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT)''')
    conn.commit()
    conn.close()

def add_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    curr = conn.cursor()
    try:
        curr.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def login_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    curr = conn.cursor()
    curr.execute("SELECT password FROM users WHERE email = ?", (email,))
    data = curr.fetchone()
    conn.close()
    if data: return data[0] == password
    return False

setup_db()

# --- 2. AUTH SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.set_page_config(page_title="Login - AI Road Detector", layout="centered")
    st.markdown("<h2 style='text-align: center;'>🔐 AI Road Damage Detector</h2>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        lemail = st.text_input("Email", key="login_email")
        lpass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", type="primary", use_container_width=True):
            if login_user(lemail, lpass):
                st.session_state.logged_in = True
                st.session_state.user_email = lemail
                st.rerun()
            else: st.error("❌ Invalid Credentials")
    with tab2:
        semail = st.text_input("Email", key="signup_email")
        spass = st.text_input("Password", type="password", key="signup_pass")
        if st.button("Create Account", use_container_width=True):
            if add_user(semail, spass): st.success("✅ Account Created! Please Login.")
            else: st.error("❌ User already exists.")
    st.stop()

# --- 3. MAIN DASHBOARD CONFIG ---
st.set_page_config(page_title="AI Road Damage Detector", layout="centered")
st.title("🛣️ AI ROAD DAMAGE DETECTOR")

if 'detection_done' not in st.session_state: st.session_state.detection_done = False
if 'show_db_view' not in st.session_state: st.session_state.show_db_view = False

# --- SIDEBAR ---
st.sidebar.header("Control Panel")
st.sidebar.info(f"👤 User: {st.session_state.user_email}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.markdown("---")
uploaded_file = st.sidebar.file_uploader("📷 Step 1: Upload Image", type=['jpg', 'jpeg', 'png'])

st.sidebar.subheader("📍 Step 2: Location Settings")
if st.sidebar.button("Get My Live Location"):
    loc = streamlit_js_eval(data_of='getCurrentPosition', key='get_loc')
    if loc:
        st.session_state.auto_lat = loc['coords']['latitude']
        st.session_state.auto_lon = loc['coords']['longitude']

u_lat = st.sidebar.number_input("Latitude", value=st.session_state.get('auto_lat', 28.6139), format="%.6f")
u_lon = st.sidebar.number_input("Longitude", value=st.session_state.get('auto_lon', 77.2090), format="%.6f")

st.sidebar.markdown("---")
st.sidebar.info("Ⓜ️ Step 3: Model Loaded")

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Step 4: Database View")
report_filter = st.sidebar.selectbox("Filter Data:", ["All Reports", "Potholes Only", "Cracks Only", "Registered Users"])
if st.sidebar.button("📊 Show Database Content"):
    st.session_state.show_db_view = True

# --- MODEL LOADING ---
@st.cache_resource
def load_yolo():
    # Check if file exists in standard path or current folder
    path = 'best.pt' 
    if not os.path.exists(path):
        path = 'C:/Users/sahil/Downloads/archive/data/runs/detect/train7/weights/best.pt'
    return YOLO(path) if os.path.exists(path) else None

yolo_model = load_yolo()

# --- MAIN LOGIC ---
if uploaded_file:
    img = Image.open(uploaded_file)
    if st.button("🚀 Run AI Detection", type="primary", use_container_width=True):
        if yolo_model:
            results = yolo_model.predict(img, conf=0.15)
            st.session_state.res_img = results[0].plot()
            labels = results[0].boxes.cls.tolist()
            st.session_state.p_count = labels.count(0)
            st.session_state.c_count = labels.count(1)
            st.session_state.det_lat, st.session_state.det_lon = u_lat, u_lon
            st.session_state.detection_done = True
        else: st.error("Model file (.pt) not found!")

    if st.session_state.detection_done:
        st.markdown("---")
        st.image(st.session_state.res_img, use_container_width=True)
        
        p, c = st.session_state.p_count, st.session_state.c_count
        if p > 0: st.warning(f"⚠️ Status: Road Damage Detected ({p} Potholes)")
        else: st.success("✅ Status: Road is Clear")

        if st.button("💾 Save Report to Database", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks) VALUES (?, ?, ?, ?, ?)", 
                         (now, st.session_state.det_lat, st.session_state.det_lon, p, c))
            conn.commit(); conn.close()
            st.success("✅ Report Saved!")

        # --- GRAPH & ANALYSIS (FIXED) ---
        st.markdown("### 📈 Detection Analysis")
        col_g1, col_g2 = st.columns(2) # Naming matching fixed
        with col_g1:
            st.write("**Damage Distribution**")
            st.bar_chart(pd.DataFrame({'Count': [p, c]}, index=['Potholes', 'Cracks']))
        with col_g2:
            st.write("**Data Summary**")
            # All values to string to fix ArrowTypeError
            summary_df = pd.DataFrame({
                "Parameter": ["Lat", "Lon", "Potholes", "Cracks"], 
                "Value": [str(st.session_state.det_lat), str(st.session_state.det_lon), str(p), str(c)]
            })
            st.table(summary_df)

        # --- MAP ---
        st.markdown("### 🗺️ Damage Location Map")
        m = folium.Map(location=[st.session_state.det_lat, st.session_state.det_lon], zoom_start=16)
        folium.Marker([st.session_state.det_lat, st.session_state.det_lon], icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, width=700, height=300)

# --- DATABASE VIEW ---
if st.session_state.show_db_view:
    st.markdown("---")
    conn = sqlite3.connect(DB_NAME)
    if report_filter == "Registered Users":
        st.subheader("👤 Registered Users")
        df_u = pd.read_sql_query("SELECT id, email, password FROM users", conn)
        # Displaying with toggle
        for _, row in df_u.iterrows():
            r1, r2, r3 = st.columns([1, 3, 2])
            r1.text(row['id'])
            r2.text(row['email'])
            p_key = f"v_{row['id']}"
            if p_key not in st.session_state: st.session_state[p_key] = False
            with r3:
                sc1, sc2 = st.columns([4, 1])
                val = row['password'] if st.session_state[p_key] else "••••••••"
                sc1.code(val, language=None)
                if sc2.button("👁️", key=f"btn_{row['id']}"):
                    st.session_state[p_key] = not st.session_state[p_key]
                    st.rerun()
            st.divider()
    else:
        st.subheader(f"📊 History: {report_filter}")
        df = pd.read_sql_query("SELECT * FROM road_logs ORDER BY id DESC", conn)
        st.dataframe(df, use_container_width=True)
    conn.close()
    if st.button("Close Database"):
        st.session_state.show_db_view = False
        st.rerun()
