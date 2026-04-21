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
import smtplib
import random
from email.message import EmailMessage
import streamlit.components.v1 as components

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="AI Road Damage Detector", layout="wide")

DB_NAME = 'road_reports_v4.db'
SENDER_EMAIL = "ss6929043@gmail.com" 
SENDER_PASS = st.secrets.get("GMAIL_PASS", "") 

if not os.path.exists("saved_results"):
    os.makedirs("saved_results")

# --- INITIALIZE SESSION STATES ---
if 'notifications' not in st.session_state: st.session_state.notifications = []
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'reset_mode' not in st.session_state: st.session_state.reset_mode = False
if 'otp_verified' not in st.session_state: st.session_state.otp_verified = False

# --- EMAIL FUNCTION ---
def send_email(subject, body, to_email=SENDER_EMAIL):
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

# --- DATABASE FUNCTIONS ---
def setup_db():
    conn = sqlite3.connect(DB_NAME)
    curr = conn.cursor()
    curr.execute('''CREATE TABLE IF NOT EXISTS road_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, lat REAL, lon REAL, 
                  potholes INTEGER, cracks INTEGER, image_path TEXT)''')
    curr.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT)''')
    conn.commit(); conn.close()

def add_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def login_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    data = conn.execute("SELECT password FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return data[0] == password if data else False

setup_db()

# --- 2. LOGIN & FORGOT PASSWORD SYSTEM ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 AI Road Damage Detector</h2>", unsafe_allow_html=True)
    
    if st.session_state.reset_mode:
        st.subheader("🔄 Reset Password")
        if not st.session_state.otp_verified:
            e_reset = st.text_input("Enter registered Email")
            if st.button("Send OTP"):
                otp = random.randint(1000, 9999)
                if send_email("Password Reset OTP", f"Your OTP is: {otp}", e_reset):
                    st.session_state.generated_otp, st.session_state.target_email = otp, e_reset
                    st.success("✅ OTP Sent to Gmail!")
            
            otp_in = st.text_input("Enter 4-Digit OTP")
            if st.button("Verify OTP"):
                if otp_in == str(st.session_state.get('generated_otp')):
                    st.session_state.otp_verified = True; st.rerun()
                else: st.error("❌ Invalid OTP")
        else:
            new_p = st.text_input("New Password", type="password")
            if st.button("Update Password"):
                conn = sqlite3.connect(DB_NAME)
                conn.execute("UPDATE users SET password=? WHERE email=?", (new_p, st.session_state.target_email))
                conn.commit(); conn.close()
                st.success("✅ Password Updated! Please Login.")
                st.session_state.reset_mode = False; st.session_state.otp_verified = False
        if st.button("Back to Login"): st.session_state.reset_mode = False; st.rerun()

    else:
        t1, t2 = st.tabs(["Login", "Sign Up"])
        with t1:
            with st.form("login_form"):
                le, lp = st.text_input("Email"), st.text_input("Password", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    if login_user(le, lp):
                        st.session_state.logged_in, st.session_state.user_email = True, le
                        send_email("👤 Login Alert", f"User {le} logged in at {datetime.now()}")
                        st.rerun()
                    else: st.error("❌ Invalid Credentials")
            if st.button("Forgot Password?"): st.session_state.reset_mode = True; st.rerun()
        with t2:
            with st.form("signup_form"):
                se, sp = st.text_input("Email"), st.text_input("Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if add_user(se, sp): st.success("✅ Account Created!")
                    else: st.error("❌ User already exists.")
    st.stop()

# --- 3. MAIN INTERFACE ---
st.title("🛣️ AI ROAD DAMAGE DETECTOR")

# Sidebar
st.sidebar.info(f"👤 User: {st.session_state.user_email}")
if st.sidebar.button("Logout"): 
    st.session_state.logged_in = False; st.rerun()

# --- 🔔 NOTIFICATION BELL ---
notif_count = len(st.session_state.notifications)
st.sidebar.markdown(f"### 🔔 Notifications: `{notif_count}`")
if notif_count > 0:
    with st.sidebar.expander("📩 Review Pending Reports"):
        for i, res in enumerate(st.session_state.notifications):
            if st.button(f"Report {i+1} from {res['user']}", key=f"notif_{i}"):
                st.session_state.active_review = res
                st.session_state.active_index = i

st.sidebar.markdown("---")
st.sidebar.subheader("📷 Step 1: Upload Image")
uploaded_file = st.sidebar.file_uploader("Choose a file", type=['jpg', 'jpeg', 'png'])

st.sidebar.subheader("📍 Step 2: Location")
if st.sidebar.button("Get My Live Location"):
    loc = streamlit_js_eval(data_of='getCurrentPosition', key='get_loc')
    if loc: st.session_state.auto_lat, st.session_state.auto_lon = loc['coords']['latitude'], loc['coords']['longitude']

u_lat = st.sidebar.number_input("Lat", value=st.session_state.get('auto_lat', 28.6139), format="%.6f")
u_lon = st.sidebar.number_input("Lon", value=st.session_state.get('auto_lon', 77.2090), format="%.6f")

st.sidebar.markdown("---")
st.sidebar.subheader("📂 Step 3: Check Reports")
st.sidebar.info("Go to 'Historical Data' tab to see saved database.")

@st.cache_resource
def load_yolo(): return YOLO('best.pt') if os.path.exists('best.pt') else None
yolo_model = load_yolo()

tab_dash, tab_hist = st.tabs(["🖥️ Dashboard", "📂 Historical Data"])

# --- TAB 1: DASHBOARD ---
with tab_dash:
    if uploaded_file:
        if st.button("🚀 Run AI Detection", type="primary", use_container_width=True):
            if yolo_model:
                img = Image.open(uploaded_file)
                results = yolo_model.predict(img, conf=0.25)
                res_img = results[0].plot()
                labels = results[0].boxes.cls.tolist()
                p_count = sum(1 for lid in labels if 'pothole' in yolo_model.names[int(lid)].lower())
                c_count = len(labels) - p_count
                
                # Notification mein add karna
                pending_report = {
                    "user": st.session_state.user_email,
                    "potholes": p_count, "cracks": c_count,
                    "lat": u_lat, "lon": u_lon, "image": res_img,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.notifications.append(pending_report)
                st.toast(f"New Notification! Found {p_count} Potholes 🔔", icon="📢")
                send_email("🚨 New Detection", f"User {st.session_state.user_email} detected {p_count} potholes.")
            else: st.error("Model file missing!")

    # --- REVIEW SECTION (MAP + INDEX) ---
    if 'active_review' in st.session_state:
        st.markdown("---")
        ar = st.session_state.active_review
        st.subheader(f"🔍 Reviewing: {ar['user']}'s Report")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.image(ar['image'], caption="AI View", use_container_width=True)
        with col2:
            st.metric("Potholes", ar['potholes'])
            st.metric("Cracks", ar['cracks'])
            
            # --- INDEX TABLE ---
            st.markdown("**📋 Data Summary**")
            summary = pd.DataFrame({"Field": ["User", "Lat", "Lon", "Time"], 
                                   "Value": [ar['user'], str(ar['lat']), str(ar['lon']), ar['time']]})
            st.table(summary)
            
            if st.button("✅ Approve & Save to Database", use_container_width=True):
                path = f"saved_results/rep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                Image.fromarray(ar['image']).save(path)
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path) VALUES (?,?,?,?,?,?)", 
                             (ar['time'], ar['lat'], ar['lon'], ar['potholes'], ar['cracks'], path))
                conn.commit(); conn.close()
                st.session_state.notifications.pop(st.session_state.active_index)
                del st.session_state.active_review
                st.success("✅ Saved Permanently!")
                st.rerun()
            
            if st.button("🗑️ Discard", use_container_width=True):
                st.session_state.notifications.pop(st.session_state.active_index)
                del st.session_state.active_review
                st.rerun()

        # --- MAP ---
        st.markdown("### 🗺️ Damage Location")
        m = folium.Map(location=[ar['lat'], ar['lon']], zoom_start=16)
        folium.Marker([ar['lat'], ar['lon']], icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, width=900, height=400)

# --- TAB 2: HISTORICAL DATA ---
with tab_hist:
    st.header("📊 History & Map Explorer")
    st.info("💡 Niche diye gye drop down button se list ka type chose kre")
    h_category = st.selectbox("drop down", ["All Reports", "Pothole Reports", "Crack Reports", "User Login Data"])
    img_config = {"image_path": st.column_config.ImageColumn("Preview", width="small")}
    conn = sqlite3.connect(DB_NAME)
    
    if h_category == "All Reports":
        st.subheader("🕳️ Pothole Reports")
        df_p = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0 ORDER BY timestamp DESC", conn)
        st.dataframe(df_p, column_config=img_config, use_container_width=True, hide_index=True)
        st.markdown("---")
        st.subheader("🚧 Crack Reports")
        df_c = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0 ORDER BY timestamp DESC", conn)
        st.dataframe(df_c, column_config=img_config, use_container_width=True, hide_index=True)
        st.markdown("---")
        st.subheader("👤 User Login Information")
        df_u = pd.read_sql_query("SELECT id, email, password FROM users", conn)
        st.dataframe(df_u, use_container_width=True, hide_index=True)
    elif h_category == "Pothole Reports":
        df = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0 ORDER BY timestamp DESC", conn)
        st.dataframe(df, column_config=img_config, use_container_width=True, hide_index=True)
    elif h_category == "Crack Reports":
        df = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0 ORDER BY timestamp DESC", conn)
        st.dataframe(df, column_config=img_config, use_container_width=True, hide_index=True)
    elif h_category == "User Login Data":
        df = pd.read_sql_query("SELECT id, email, password FROM users", conn)
        st.dataframe(df, use_container_width=True, hide_index=True)
    conn.close()
