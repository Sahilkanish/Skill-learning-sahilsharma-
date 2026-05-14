import streamlit as st
from ultralytics import YOLO
from PIL import Image
import sqlite3
import pandas as pd
from datetime import datetime
import folium
from streamlit_folium import st_folium
import os
import smtplib
import random
from email.message import EmailMessage
from streamlit_geolocation import streamlit_geolocation

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="AI Road Damage Detector", layout="wide")

DB_NAME = 'road_reports_v4.db'
ADMIN_EMAIL = "ss6929043@gmail.com"
SENDER_EMAIL = "ss6929043@gmail.com"
SENDER_PASS = st.secrets.get("GMAIL_PASS", "") 

if not os.path.exists("saved_results"):
    os.makedirs("saved_results")

# --- INITIALIZE SESSION STATES ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'reset_mode' not in st.session_state: st.session_state.reset_mode = False
if 'detection_data' not in st.session_state: st.session_state.detection_data = None
if 'active_review' not in st.session_state: st.session_state.active_review = False
if 'auto_lat' not in st.session_state: st.session_state.auto_lat = 28.6139
if 'auto_lon' not in st.session_state: st.session_state.auto_lon = 77.2090

# --- DATABASE SETUP ---
def setup_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS road_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, lat REAL, lon REAL, 
                 potholes INTEGER, cracks INTEGER, image_path TEXT, user_email TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS pending_reports 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, lat REAL, lon REAL, 
                 potholes INTEGER, cracks INTEGER, timestamp TEXT, image_path TEXT)''')
    conn.commit()
    conn.close()

setup_db()

# --- LOGIN / SIGNUP UI ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 AI Road Damage Detection System</h2>", unsafe_allow_html=True)
    
    if st.session_state.reset_mode:
        st.subheader("🔄 Reset Account Password")
        e_reset = st.text_input("Enter Registered Email")
        if st.button("Send Verification OTP"):
            st.info("OTP functionality requires configured SENDER_EMAIL.")
        if st.button("Back to Login"): 
            st.session_state.reset_mode = False
            st.rerun()
    else:
        tab_login, tab_signup = st.tabs(["Login", "Create Account"])
        with tab_login:
            with st.form("login_form"):
                le = st.text_input("Email Address")
                lp = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In"):
                    conn = sqlite3.connect(DB_NAME)
                    d = conn.execute("SELECT password FROM users WHERE email=?", (le,)).fetchone()
                    conn.close()
                    if d and d[0] == lp:
                        st.session_state.logged_in = True
                        st.session_state.user_email = le
                        st.rerun()
                    else: st.error("❌ Invalid email or password.")
            if st.button("Forgot Password?"): 
                st.session_state.reset_mode = True
                st.rerun()
        
        with tab_signup:
            with st.form("signup_form"):
                ne = st.text_input("New Email")
                npw = st.text_input("New Password", type="password")
                ncp = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Register"):
                    if ne and npw == ncp:
                        try:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO users (email, password) VALUES (?,?)", (ne, npw))
                            conn.commit(); conn.close()
                            st.success("✅ Registration successful! Please switch to Login tab.")
                        except: st.error("❌ This email is already registered.")
                    else: st.error("❌ Passwords do not match.")
    st.stop()

# --- SIDEBAR NAVIGATION ---
is_admin = (st.session_state.user_email == ADMIN_EMAIL)

with st.sidebar:
    st.title("Settings & Tools")
    st.write(f"Logged in as: **{st.session_state.user_email}**")
    
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
    
    st.markdown("---")
    if is_admin:
        st.subheader("🔔 Admin Notifications")
        conn = sqlite3.connect(DB_NAME)
        pending = pd.read_sql_query("SELECT * FROM pending_reports", conn)
        conn.close()
        st.write(f"Pending Reviews: `{len(pending)}`")
        if not pending.empty:
            for idx, row in pending.iterrows():
                if st.button(f"Review Report #{row['id']}", key=f"rev_{row['id']}"):
                    st.session_state.detection_data = row.to_dict()
                    st.session_state.active_review = True
                    st.session_state.active_index = row['id']
                    st.rerun()

    st.markdown("---")
    st.subheader("📤 Data Input")
    uploaded_file = st.file_uploader("Upload Infrastructure Image", type=['jpg', 'jpeg', 'png'])
    
    loc = streamlit_geolocation()
    if st.button("Fetch Current GPS Location", use_container_width=True):
        if loc and loc.get("latitude"):
            st.session_state.auto_lat = float(loc["latitude"])
            st.session_state.auto_lon = float(loc["longitude"])
            st.success("Location Synced!")

    u_lat = st.number_input("Latitude", value=st.session_state.auto_lat, format="%.6f")
    u_lon = st.number_input("Longitude", value=st.session_state.auto_lon, format="%.6f")

# --- MAIN APP INTERFACE ---
@st.cache_resource
def load_yolo(): 
    return YOLO('best.pt') if os.path.exists('best.pt') else None

yolo_model = load_yolo()

st.title("🛣️ Smart Infrastructure Monitoring")
tab_dash, tab_hist, tab_stats = st.tabs(["📊 Detection Dashboard", "📂 Historical Archives", "📈 Model Analytics"])

# --- TAB 1: DASHBOARD ---
with tab_dash:
    if not st.session_state.detection_data:
        st.info("💡 **Welcome to the Dashboard.** Please upload an image and provide coordinates via the sidebar to begin analysis.")

    if uploaded_file and st.button("Execute AI Analysis", type="primary", use_container_width=True):
        img = Image.open(uploaded_file)
        res = yolo_model.predict(img, conf=0.25)
        res_img = res[0].plot()
        lbls = res[0].boxes.cls.tolist()
        p_cnt = sum(1 for lid in lbls if 'pothole' in yolo_model.names[int(lid)].lower())
        c_cnt = len(lbls) - p_cnt
        path = f"saved_results/res_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        Image.fromarray(res_img).save(path)
        
        st.session_state.detection_data = {
            "user_email": st.session_state.user_email, "potholes": p_cnt, "cracks": c_cnt,
            "lat": u_lat, "lon": u_lon, "image_path": path, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.active_review = False
        
        if not is_admin:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO pending_reports (user_email, lat, lon, potholes, cracks, timestamp, image_path) VALUES (?,?,?,?,?,?,?)", 
                         (st.session_state.user_email, u_lat, u_lon, p_cnt, c_cnt, st.session_state.detection_data["timestamp"], path))
            conn.commit(); conn.close()
            st.success("✅ Report submitted for Administrator review.")

    if st.session_state.detection_data:
        det = st.session_state.detection_data
        col_img, col_info = st.columns([1.5, 1])
        with col_img:
            st.image(det['image_path'], caption="AI Detection Result", use_container_width=True)
        with col_info:
            st.markdown("### 📋 Analysis Results")
            st.write(f"**Submitted by:** {det['user_email']}")
            st.write(f"**Timestamp:** {det['timestamp']}")
            st.metric("Potholes Detected", det['potholes'])
            st.metric("Cracks Detected", det['cracks'])
            
            if det['potholes'] > 3: st.error("CRITICAL: Immediate Road Repair Required")
            elif det['potholes'] > 0: st.warning("WARNING: Maintenance Recommended")
            else: st.success("NORMAL: Road condition is stable")

            if is_admin:
                b1, b2 = st.columns(2)
                if st.session_state.active_review:
                    if b1.button("Verify & Archive", key="admin_save"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path, user_email) VALUES (?,?,?,?,?,?,?)", 
                                     (det['timestamp'], det['lat'], det['lon'], det['potholes'], det['cracks'], det['image_path'], det['user_email']))
                        conn.execute("DELETE FROM pending_reports WHERE id=?", (st.session_state.active_index,))
                        conn.commit(); conn.close()
                        st.success("Record Archived!"); st.session_state.detection_data = None; st.rerun()
                    if b2.button("Reject Report", key="admin_del"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM pending_reports WHERE id=?", (st.session_state.active_index,))
                        conn.commit(); conn.close()
                        st.session_state.detection_data = None; st.rerun()
                else:
                    if b1.button("Save to Database", key="user_save"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path, user_email) VALUES (?,?,?,?,?,?,?)", 
                                     (det['timestamp'], det['lat'], det['lon'], det['potholes'], det['cracks'], det['image_path'], st.session_state.user_email))
                        conn.commit(); conn.close()
                        st.success("Saved Successfully!"); st.session_state.detection_data = None; st.rerun()

        st.markdown("---")
        m = folium.Map(location=[det['lat'], det['lon']], zoom_start=15)
        folium.Marker([det['lat'], det['lon']], popup="Detection Point").add_to(m)
        st_folium(m, width=1000, height=350, key="dash_map")

# --- TAB 2: HISTORICAL DATA ---
with tab_hist:
    if is_admin:
        st.header("📂 Data Management Center")
        st.markdown("Filter and manage historical infrastructure records stored in the system.")
        
        filter_type = st.selectbox("Filter by Category", ["All Records", "Potholes Only", "Cracks Only", "User Accounts"])
        
        if st.button("Fetch Archive Data", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            if filter_type == "User Accounts":
                st.dataframe(pd.read_sql_query("SELECT id, email FROM users", conn), use_container_width=True)
            else:
                query = "SELECT * FROM road_logs ORDER BY timestamp DESC"
                df = pd.read_sql_query(query, conn)
                st.dataframe(df, use_container_width=True)
                for _, row in df.iterrows():
                    with st.expander(f"Record {row['id']} - {row['timestamp']}"):
                        st.image(row['image_path'])
            conn.close()
    else: st.info("🔒 This section is restricted to authorized Administrators.")

# --- TAB 3: PERFORMANCE ---
with tab_stats:
    if is_admin:
        st.markdown("""
        ### 📊 Performance Analysis Overview
        The **AI Road Damage Detector** utilizes a state-of-the-art **YOLO** architecture, 
        specifically fine-tuned on a diverse dataset of road infrastructure. 
        
        The model is evaluated based on its ability to accurately localize and classify road distress 
        features like **Potholes** and **Cracks** in real-time environments. Below are the key 
        performance indicators and training results.
        """)

        if st.button("🔍 Generate Detailed Performance Report", use_container_width=True, type="primary"):
            st.markdown("---")
            st.subheader("📈 Model Training Metrics")
            c1, c2 = st.columns(2)
            c1.metric("Training mAP50", "86.5%")
            c2.metric("Validation mAP50", "81.4%")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Precision", "85.8%"); m2.metric("Recall", "75.2%"); m3.metric("Inference", "15ms")

            if os.path.exists('results.png'):
                st.image('results.png', caption='Accuracy & Loss Curves', use_container_width=True)
            
            st.info("💡 **Conclusion:** Achieving 81.4% accuracy, the model demonstrates high reliability for real-world deployment.")
            
            st.markdown("#### 🏆 Strategic Value")
            v1, v2, v3 = st.columns(3)
            with v1: st.success("🛡️ **Public Safety**\n\nReducing hazards.")
            with v2: st.success("💰 **Fiscal Savings**\n\nLower maintenance.")
            with v3: st.success("📢 **Transparency**\n\nDigitized records.")
    else: st.info("🔒 Administrative access required to view performance metrics.")
