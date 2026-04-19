import streamlit as st
from ultralytics import YOLO
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
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

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="AI Road Damage Detector", layout="wide")

DB_NAME = 'road_reports_v4.db'
SENDER_EMAIL = "ss6929043@gmail.com" 
SENDER_PASS = st.secrets.get("GMAIL_PASS", "") 

# --- FUNCTION TO GET LOCATION FROM IMAGE METADATA ---
def get_image_location(image):
    try:
        info = image._getexif()
        if not info:
            return None
        
        geotagging = {}
        for (tag, value) in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == 'GPSInfo':
                for (t, v) in value.items():
                    sub_decoded = GPSTAGS.get(t, t)
                    geotagging[sub_decoded] = v
        
        if 'GPSLatitude' in geotagging and 'GPSLongitude' in geotagging:
            def convert_to_degrees(value):
                d = float(value[0])
                m = float(value[1])
                s = float(value[2])
                return d + (m / 60.0) + (s / 3600.0)

            lat = convert_to_degrees(geotagging['GPSLatitude'])
            lon = convert_to_degrees(geotagging['GPSLongitude'])
            if geotagging.get('GPSLatitudeRef') == 'S': lat = -lat
            if geotagging.get('GPSLongitudeRef') == 'W': lon = -lon
            return lat, lon
    except Exception:
        return None
    return None

# --- DATABASE SETUP ---
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
    try:
        conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def login_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    data = conn.execute("SELECT password FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if data: return data[0] == password
    return False

def send_otp_email(receiver_email, otp):
    try:
        msg = EmailMessage()
        msg.set_content(f"Your OTP for AI Road Detector password reset is: {otp}")
        msg['Subject'] = 'Password Reset OTP'
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASS)
            smtp.send_message(msg)
        return True
    except: return False

setup_db()

# --- 2. LOGIN & RESET SYSTEM ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'reset_mode' not in st.session_state: st.session_state.reset_mode = False
if 'otp_verified' not in st.session_state: st.session_state.otp_verified = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 AI Road Damage Detector</h2>", unsafe_allow_html=True)

    if st.session_state.reset_mode:
        st.subheader("🔄 Reset Password")
        if not st.session_state.otp_verified:
            email_to_reset = st.text_input("Enter registered Email")
            if st.button("Send OTP"):
                conn = sqlite3.connect(DB_NAME)
                user = conn.execute("SELECT id FROM users WHERE email=?", (email_to_reset,)).fetchone()
                conn.close()
                if user:
                    otp = random.randint(1000, 9999)
                    if send_otp_email(email_to_reset, otp):
                        st.session_state.generated_otp = otp
                        st.session_state.target_email = email_to_reset
                        st.success("✅ OTP sent to your Gmail!")
                    else: st.error("❌ Failed to send email.")
                else: st.error("❌ Email not found.")
            
            otp_in = st.text_input("Enter 4-Digit OTP")
            if st.button("Verify OTP"):
                if otp_in == str(st.session_state.get('generated_otp')):
                    st.session_state.otp_verified = True
                    st.rerun()
                else: st.error("❌ Invalid OTP")
        else:
            new_p = st.text_input("New Password", type="password")
            conf_p = st.text_input("Confirm Password", type="password")
            if st.button("Update Password"):
                if new_p == conf_p and new_p != "":
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("UPDATE users SET password=? WHERE email=?", (new_p, st.session_state.target_email))
                    conn.commit()
                    conn.close()
                    st.success("✅ Success! Please Login.")
                    st.session_state.reset_mode = st.session_state.otp_verified = False
                else: st.error("❌ Passwords don't match.")
        
        if st.button("Back to Login"): 
            st.session_state.reset_mode = False
            st.rerun()
    else:
        t1, t2 = st.tabs(["Login", "Sign Up"])
        with t1:
            with st.form("l_form"):
                le = st.text_input("Email",)
                lp = st.text_input("Password", type="password")
                if st.form_submit_button("Login", type="primary", use_container_width=True):
                    if login_user(le, lp):
                        st.session_state.logged_in, st.session_state.user_email = True, le
                        st.rerun()
                    else: st.error("❌ Invalid Credentials")
            if st.button("Forgot Password?"):
                st.session_state.reset_mode = True
                st.rerun()
        with t2:
            with st.form("s_form"):
                se, sp = st.text_input("Email"), st.text_input("Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if add_user(se, sp): st.success("✅ Created! Please Login.")
                    else: st.error("❌ User already exists.")
    st.stop()

# --- 3. MAIN INTERFACE ---
st.title("🛣️ AI ROAD DAMAGE DETECTOR")

# Sidebar
st.sidebar.info(f"👤 User: {st.session_state.user_email}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.markdown("---")
uploaded_file = st.sidebar.file_uploader("📷 Step 1: Upload Image", type=['jpg', 'jpeg', 'png'])

# AUTO-FILL LOCATION FROM IMAGE
if uploaded_file:
    img_temp = Image.open(uploaded_file)
    coords = get_image_location(img_temp)
    if coords:
        st.session_state.auto_lat, st.session_state.auto_lon = coords
        st.sidebar.success("📍 Location extracted from Image!")

# Location Sidebar
st.sidebar.subheader("📍 Step 2: Location")
if st.sidebar.button("Get My Live Location"):
    loc = streamlit_js_eval(data_of='getCurrentPosition', key='get_loc')
    if loc:
        st.session_state.auto_lat, st.session_state.auto_lon = loc['coords']['latitude'], loc['coords']['longitude']

u_lat = st.sidebar.number_input("Lat", value=st.session_state.get('auto_lat', 28.6139), format="%.6f")
u_lon = st.sidebar.number_input("Lon", value=st.session_state.get('auto_lon', 77.2090), format="%.6f")

# --- STEP 3 SIDEBAR ADDITION ---
st.sidebar.markdown("---")
st.sidebar.subheader("📂 Step 3: Check Reports")
st.sidebar.info("All reports check karne ke liye 'Historical Data' tab par click karein.")

# Model Loading
@st.cache_resource
def load_yolo():
    return YOLO('best.pt') if os.path.exists('best.pt') else None
yolo_model = load_yolo()

# TABS
tab_dash, tab_hist = st.tabs(["🖥️ Dashboard", "📂 Historical Data"])

# --- TAB 1: DASHBOARD ---
with tab_dash:
    if uploaded_file:
        st.success("✅ Image uploaded!")
        if st.button("🚀 Run AI Detection", type="primary", use_container_width=True):
            if yolo_model:
                img = Image.open(uploaded_file)
                results = yolo_model.predict(img, conf=0.25, iou=0.45) 
                st.session_state.res_img = results[0].plot()
                labels = results[0].boxes.cls.tolist()
                class_names = yolo_model.names
                p_count = 0
                c_count = 0
                for label_id in labels:
                    name = class_names[label_id].lower()
                    if 'pothole' in name:
                        p_count += 1
                    else:
                        c_count += 1
                st.session_state.p_count = p_count
                st.session_state.c_count = c_count
                st.session_state.det_lat, st.session_state.det_lon = u_lat, u_lon
                st.session_state.detection_done = True
            else: st.error("Model file (best.pt) not found!")

    if st.session_state.get('detection_done'):
        st.markdown("---")
        cl, cr = st.columns([2, 1])
        p, c = st.session_state.p_count, st.session_state.c_count
        with cl:
            st.image(st.session_state.res_img, caption="AI Detection Result", use_container_width=True)
        with cr:
            st.subheader("📋 Detection Results")
            status_color = "red" if p > 0 else "green"
            status_txt = "DANGER (Potholes)" if p > 0 else "SAFE"
            st.markdown(f"<h3 style='color:{status_color};'>Status: {status_txt}</h3>", unsafe_allow_html=True)
            st.metric("🕳️ Potholes Found", p)
            st.metric("🚧 Cracks Found", c)
            if st.button("💾 Save Report to Database", use_container_width=True):
                conn = sqlite3.connect(DB_NAME)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks) VALUES (?, ?, ?, ?, ?)", 
                             (now, st.session_state.det_lat, st.session_state.det_lon, p, c))
                conn.commit(); conn.close()
                st.success("✅ Saved!")

        st.markdown("### 📈 Detection Analysis")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.write("**Damage Distribution (Graph)**")
            chart_data = pd.DataFrame({'Count': [p, c]}, index=['Potholes', 'Cracks'])
            st.bar_chart(chart_data)
        with col_g2:
            st.write("**Data Summary (Index)**")
            summary_df = pd.DataFrame({
                "Parameter": ["Latitude", "Longitude", "Potholes Found", "Cracks Found"], 
                "Value": [str(st.session_state.det_lat), str(st.session_state.det_lon), str(p), str(c)]
            })
            st.table(summary_df)

        st.markdown("### 🗺️ Damage Location Map")
        m = folium.Map(location=[st.session_state.det_lat, st.session_state.det_lon], zoom_start=16)
        folium.Marker([st.session_state.det_lat, st.session_state.det_lon], popup=f"P: {p}, C: {c}", icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, width=900, height=400)

# --- TAB 2: HISTORICAL DATA ---
with tab_hist:
    st.header("📊 History & Map Explorer")
    
    # Instruction message added here
    st.info("💡 Niche diye gye drop down button se list ka type chose kre")
    
    h_category = st.selectbox("Select Category:", ["All Reports", "Pothole Reports", "Crack Reports", "User Login Data"])

    conn = sqlite3.connect(DB_NAME)
    
    if h_category == "All Reports":
        st.subheader("🕳️ Pothole Reports")
        df_p = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0 ORDER BY timestamp DESC", conn)
        st.dataframe(df_p, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("🚧 Crack Reports")
        df_c = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0 ORDER BY timestamp DESC", conn)
        st.dataframe(df_c, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("👤 User Login Information")
        df_u = pd.read_sql_query("SELECT id, email, password FROM users", conn)
        st.dataframe(df_u, use_container_width=True)

    elif h_category == "Pothole Reports":
        df = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0 ORDER BY timestamp DESC", conn)
        st.dataframe(df, use_container_width=True)

    elif h_category == "Crack Reports":
        df = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0 ORDER BY timestamp DESC", conn)
        st.dataframe(df, use_container_width=True)

    elif h_category == "User Login Data":
        df = pd.read_sql_query("SELECT id, email, password FROM users", conn)
        st.dataframe(df, use_container_width=True)
    
    conn.close()
