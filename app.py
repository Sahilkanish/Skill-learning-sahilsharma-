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

# --- FUNCTIONS ---
def send_email(subject, body, to_email):
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASS)
            smtp.send_message(msg)
        return True
    except: return False

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
    conn.commit(); conn.close()

setup_db()

# --- 2. LOGIN SYSTEM ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 AI Road Damage Detector</h2>", unsafe_allow_html=True)
    
    if st.session_state.reset_mode:
        st.subheader("🔄 Reset Password")
        e_reset = st.text_input("Enter Email")
        if st.button("Send OTP"):
            otp = random.randint(1000, 9999)
            if send_email("Reset OTP", f"Your OTP: {otp}", e_reset):
                st.session_state.generated_otp, st.session_state.target_email = otp, e_reset
                st.success("OTP Sent!")
        
        u_otp = st.text_input("Enter OTP")
        new_pw = st.text_input("New Password", type="password")
        if st.button("Update"):
            if str(u_otp) == str(st.session_state.get('generated_otp')):
                conn = sqlite3.connect(DB_NAME)
                conn.execute("UPDATE users SET password=? WHERE email=?", (new_pw, st.session_state.target_email))
                conn.commit(); conn.close()
                st.success("Done!"); st.session_state.reset_mode = False; st.rerun()
        if st.button("Back"): st.session_state.reset_mode = False; st.rerun()
    
    else:
        t1, t2 = st.tabs(["Login", "Sign Up"])
        with t1:
            with st.form("login_form"):
                le, lp = st.text_input("Email"), st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    conn = sqlite3.connect(DB_NAME)
                    d = conn.execute("SELECT password FROM users WHERE email=?", (le,)).fetchone()
                    conn.close()
                    if d and d[0] == lp:
                        st.session_state.logged_in, st.session_state.user_email = True, le
                        if le != ADMIN_EMAIL: send_email("Login Alert", f"User {le} logged in", ADMIN_EMAIL)
                        st.rerun()
                    else: st.error("❌ Invalid Credentials")
            if st.button("Forgot Password?"): st.session_state.reset_mode = True; st.rerun()
        
        with t2:
            with st.form("signup_form"):
                ne, npw, ncp = st.text_input("Email"), st.text_input("Pass", type="password"), st.text_input("Confirm", type="password")
                if st.form_submit_button("Sign Up"):
                    if ne and npw == ncp:
                        try:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO users (email, password) VALUES (?,?)", (ne, npw))
                            conn.commit(); conn.close()
                            st.success("✅ Account Created! Now please Login.")
                        except: st.error("❌ Email already exists!")
                    else: st.error("❌ Passwords do not match or fields are empty.")
    st.stop()

# --- 3. SIDEBAR WITH STEPS ---
is_admin = (st.session_state.user_email == ADMIN_EMAIL)

with st.sidebar:
    st.markdown(f"<h3 style='text-align: center; color: #3498db;'>Welcome, {st.session_state.user_email.split('@')[0]}</h3>", unsafe_allow_html=True)
    if st.button("🚪 Logout", use_container_width=True): 
        st.session_state.clear()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 🛠️ NAVIGATION STEPS")
    
    # STEP 1
    st.markdown("#### 📷 **Step 1: Upload Image**")
    uploaded_file = st.file_uploader("Upload road image", type=['jpg', 'jpeg', 'png'], label_visibility="collapsed")
    
    st.markdown("---")
    
    # STEP 2
    st.markdown("#### 📍 **Step 2: Get Location**")
    loc = streamlit_geolocation()
    if st.button("Capture Live GPS", use_container_width=True):
        if loc and loc.get("latitude"):
            st.session_state.auto_lat = float(loc["latitude"])
            st.session_state.auto_lon = float(loc["longitude"])
            st.sidebar.success("📍 GPS Updated!")
            st.rerun()
    u_lat = st.number_input("Lat", value=st.session_state.auto_lat, format="%.6f")
    u_lon = st.number_input("Lon", value=st.session_state.auto_lon, format="%.6f")

    st.markdown("---")

    # STEP 3
    st.markdown("#### 📂 **Step 3: Historical Data**")
    if is_admin:
        st.caption("Admin: Access records in the 'Historical Data' tab.")
    else:
        st.caption("🔒 View-only for Admin.")

    st.markdown("---")

    # STEP 4
    st.markdown("#### 📈 **Step 4: Performance**")
    if is_admin:
        st.caption("Admin: View accuracy in the 'Performance Metrics' tab.")
    else:
        st.caption("🔒 View-only for Admin.")

    if is_admin:
        st.markdown("---")
        conn = sqlite3.connect(DB_NAME); pending = pd.read_sql_query("SELECT * FROM pending_reports", conn); conn.close()
        st.markdown(f"### 🔔 Notifications: `{len(pending)}`")
        if len(pending) > 0:
            with st.expander("📩 Review Reports"):
                for i, row in pending.iterrows():
                    if st.button(f"Report {row['id']} - {row['user_email']}", key=f"n_{row['id']}"):
                        st.session_state.detection_data = row.to_dict()
                        st.session_state.active_review = True 
                        st.session_state.active_index = row['id']
                        st.rerun()

# --- 4. MAIN DASHBOARD ---
@st.cache_resource
def load_yolo(): return YOLO('best.pt') if os.path.exists('best.pt') else None
yolo_model = load_yolo()

st.markdown("<h2 style='text-align: center;'>🛣️ AI ROAD DAMAGE DETECTOR</h2>", unsafe_allow_html=True)
tab_dash, tab_hist, tab_stats = st.tabs(["🖥️ Dashboard", "📂 Historical Data", "📈 Performance Metrics"])

with tab_dash:
    if not st.session_state.detection_data:
        st.info("👋 Follow Step 1 & 2 in the sidebar to start detection.")

    if uploaded_file and st.button("🚀 Run AI Detection", type="primary", use_container_width=True):
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
                         (st.session_state.user_email, u_lat, u_lon, p_cnt, c_cnt, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), path))
            conn.commit(); conn.close()
            st.success("✅ Report sent to Admin!")

    if st.session_state.detection_data:
        det = st.session_state.detection_data
        c_l, c_r = st.columns([1.5, 1])
        with c_l: 
            st.image(det['image_path'], caption="AI Detection Result", use_container_width=True)
        with c_r:
            st.table(pd.DataFrame({"Param": ["User", "Lat", "Lon", "Potholes", "Cracks"], 
                                   "Value": [det.get('user_email'), det['lat'], det['lon'], det['potholes'], det['cracks']]}))
            
            if det['potholes'] > 3: st.error("🔴 **ROAD IS DAMAGED**")
            elif det['potholes'] >= 1: st.warning("🟠 **ROAD REPAIR NEEDED**")
            else: st.success("🟢 **ROAD IS GOOD**")

            if is_admin:
                b_col1, b_col2 = st.columns(2)
                if st.session_state.active_review:
                    if b_col1.button("✅ Approve", use_container_width=True):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path, user_email) VALUES (?,?,?,?,?,?,?)", 
                                     (det['timestamp'], det['lat'], det['lon'], det['potholes'], det['cracks'], det['image_path'], det['user_email']))
                        conn.execute("DELETE FROM pending_reports WHERE id=?", (st.session_state.active_index,))
                        conn.commit(); conn.close()
                        st.success("Approved!"); st.session_state.detection_data = None; st.session_state.active_review = False; st.rerun()
                    if b_col2.button("❌ Discard", use_container_width=True):
                        conn = sqlite3.connect(DB_NAME); conn.execute("DELETE FROM pending_reports WHERE id=?", (st.session_state.active_index,))
                        conn.commit(); conn.close()
                        st.session_state.detection_data = None; st.session_state.active_review = False; st.rerun()
                else:
                    if b_col1.button("💾 Save Record", use_container_width=True):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path, user_email) VALUES (?,?,?,?,?,?,?)", 
                                     (det['timestamp'], det['lat'], det['lon'], det['potholes'], det['cracks'], det['image_path'], st.session_state.user_email))
                        conn.commit(); conn.close()
                        st.success("Saved!"); st.session_state.detection_data = None; st.rerun()

        st.markdown("---")
        m = folium.Map(location=[det['lat'], det['lon']], zoom_start=16)
        folium.Marker([det['lat'], det['lon']], icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, width=1100, height=400, key="main_map")

# --- TAB 2: HISTORY ---
with tab_hist:
    if is_admin:
        st.header("📂 Data Records")
        report_type = st.selectbox("Select Report Category", ["All Reports", "Crack", "Pothole", "User Login Records"], key="hist_select")
        if st.button("🔍 Show Records", use_container_width=True, type="primary"):
            conn = sqlite3.connect(DB_NAME)
            if report_type == "All Reports":
                df = pd.read_sql_query("SELECT * FROM road_logs ORDER BY timestamp DESC", conn)
            elif report_type == "Crack":
                df = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0", conn)
            elif report_type == "Pothole":
                df = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0", conn)
            else:
                df = pd.read_sql_query("SELECT email FROM users", conn)
            st.dataframe(df, use_container_width=True)
            if 'image_path' in df.columns:
                for img_p in df['image_path'].dropna():
                    if os.path.exists(img_p): st.image(img_p, width=300)
            conn.close()
    else: st.info("🔒 Admin Only Access")

# --- TAB 3: PERFORMANCE ---
with tab_stats:
    if is_admin:
        st.header("📈 Model Performance")
        c1, c2 = st.columns(2)
        c1.metric("Model Precision", "85.8%")
        c2.metric("Validation mAP", "81.4%")
        if os.path.exists('results.png'): st.image('results.png', caption='Training Curves', use_container_width=True)
        st.success("Model is optimized for deployment.")
    else: st.info("🔒 Admin Only Access")
