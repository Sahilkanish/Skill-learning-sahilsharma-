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
if 'active_review' not in st.session_state: st.session_state.active_review = None
if 'auto_lat' not in st.session_state: st.session_state.auto_lat = 28.6139
if 'auto_lon' not in st.session_state: st.session_state.auto_lon = 77.2090

# --- EMAIL FUNCTION ---
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

# --- DATABASE SETUP ---
def setup_db():
    conn = sqlite3.connect(DB_NAME)
    curr = conn.cursor()
    curr.execute('''CREATE TABLE IF NOT EXISTS road_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, lat REAL, lon REAL, 
                  potholes INTEGER, cracks INTEGER, image_path TEXT, user_email TEXT)''')
    curr.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT)''')
    # Persistence ke liye notification table
    curr.execute('''CREATE TABLE IF NOT EXISTS pending_reports 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT, lat REAL, lon REAL, 
                  potholes INTEGER, cracks INTEGER, timestamp TEXT, image_path TEXT)''')
    conn.commit(); conn.close()

def login_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    data = conn.execute("SELECT password FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return data[0] == password if data else False

setup_db()

# --- 2. LOGIN, SIGN UP & RESET SYSTEM ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 AI Road Damage Detector</h2>", unsafe_allow_html=True)
    
    if st.session_state.reset_mode:
        st.subheader("🔄 Reset Password")
        e_reset = st.text_input("Enter registered Email")
        if st.button("Send OTP"):
            otp = random.randint(1000, 9999)
            if send_email("Password Reset OTP", f"Your OTP is: {otp}", e_reset):
                st.session_state.generated_otp, st.session_state.target_email = otp, e_reset
                st.success("✅ OTP Sent to your email!")
        
        user_otp = st.text_input("Enter 4-Digit OTP")
        new_pw = st.text_input("Enter New Password", type="password")
        if st.button("Update Password"):
            if str(user_otp) == str(st.session_state.get('generated_otp')):
                conn = sqlite3.connect(DB_NAME)
                conn.execute("UPDATE users SET password = ? WHERE email = ?", (new_pw, st.session_state.target_email))
                conn.commit(); conn.close()
                st.success("✨ Password Updated!")
                st.session_state.reset_mode = False
            else: st.error("❌ Invalid OTP")
        if st.button("Back to Login"): st.session_state.reset_mode = False; st.rerun()

    else:
        tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
        with tab_login:
            with st.form("login_form"):
                le = st.text_input("Email", value="") 
                lp = st.text_input("Password", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    if login_user(le, lp):
                        st.session_state.logged_in, st.session_state.user_email = True, le
                        if le != ADMIN_EMAIL:
                            send_email("🔔 New User Login Alert", f"User {le} ne login kiya hai.", ADMIN_EMAIL)
                        st.rerun()
                    else: st.error("❌ Invalid Credentials")
            if st.button("Forgot Password?"): st.session_state.reset_mode = True; st.rerun()

        with tab_signup:
            st.subheader("📝 Create New Account")
            with st.form("signup_form"):
                new_email = st.text_input("Email Address")
                new_password = st.text_input("Create Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Sign Up", use_container_width=True):
                    if new_email and new_password == confirm_password:
                        try:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO users (email, password) VALUES (?,?)", (new_email, new_password))
                            conn.commit(); conn.close()
                            st.success("✅ Account created!")
                        except: st.error("❌ Email exists!")
                    else: st.error("❌ Check details!")
    st.stop()

# --- 3. MAIN INTERFACE ---
is_admin = (st.session_state.user_email == ADMIN_EMAIL)

with st.sidebar:
    st.info(f"👤 User: {st.session_state.user_email}")
    if st.button("Logout"): 
        st.session_state.logged_in = False; st.rerun()
    
    st.markdown("---")
    if is_admin:
        conn = sqlite3.connect(DB_NAME)
        pending_reports = pd.read_sql_query("SELECT * FROM pending_reports", conn)
        conn.close()
        
        notif_count = len(pending_reports)
        st.markdown(f"### 🔔 Notifications: `{notif_count}`")
        if notif_count > 0:
            with st.expander("📩 Review Pending Reports", expanded=True):
                for i, row in pending_reports.iterrows():
                    if st.button(f"Report {row['id']} from {row['user_email']}", key=f"notif_{row['id']}", use_container_width=True):
                        st.session_state.active_review = row.to_dict()
                        st.session_state.detection_data = row.to_dict()
                        st.session_state.active_index = row['id']

    st.markdown("---")
    uploaded_file = st.file_uploader("📷 Step 1: Upload Image", type=['jpg', 'jpeg', 'png'])
    
    
    # Button click pe hi location fetch karo
with st.sidebar:

    st.markdown("---")

    # Button sidebar me hi rahega
    if st.button("📍 Get My Live Location", use_container_width=True):
        st.session_state.get_loc = True

    # Location fetch logic
    if st.session_state.get("get_loc", False):
        from streamlit_geolocation import streamlit_geolocation
        location = streamlit_geolocation()

        if location:
            st.session_state.auto_lat = location["latitude"]
            st.session_state.auto_lon = location["longitude"]
            st.success("✅ Live Location Updated")
            st.session_state.get_loc = False
        else:
            st.warning("📍 Location allow karo browser me")

    # Always show values in sidebar
    u_lat = st.number_input("Lat", value=st.session_state.auto_lat, format="%.6f")
    u_lon = st.number_input("Lon", value=st.session_state.auto_lon, format="%.6f")

    st.markdown("---")
    st.success("✅ **Step 3:** Report check karne ke liye **Historical Data** tab par click karein")
    

@st.cache_resource
def load_yolo(): return YOLO('best.pt') if os.path.exists('best.pt') else None
yolo_model = load_yolo()

st.markdown("<h2 style='text-align: center;'>🛣️ AI ROAD DAMAGE DETECTOR</h2>", unsafe_allow_html=True)
tab_dash, tab_hist = st.tabs(["🖥️ Dashboard", "📂 Historical Data"])

# --- TAB 1: DASHBOARD ---
with tab_dash:
    if uploaded_file and st.button("🚀 Run AI Detection", type="primary"):
        img = Image.open(uploaded_file)
        results = yolo_model.predict(img, conf=0.25)
        res_img = results[0].plot()
        labels = results[0].boxes.cls.tolist()
        p_count = sum(1 for lid in labels if 'pothole' in yolo_model.names[int(lid)].lower())
        c_count = len(labels) - p_count
        
        path = f"saved_results/res_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        Image.fromarray(res_img).save(path)
        
        st.session_state.active_review = None
        st.session_state.detection_data = {
            "user_email": st.session_state.user_email, "potholes": p_count, "cracks": c_count,
            "lat": u_lat, "lon": u_lon, "image_path": path, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if not is_admin:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO pending_reports (user_email, lat, lon, potholes, cracks, timestamp, image_path) VALUES (?,?,?,?,?,?,?)",
                         (st.session_state.user_email, u_lat, u_lon, p_count, c_count, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), path))
            conn.commit(); conn.close()
            st.toast("Report sent to Admin!")

    if st.session_state.detection_data:
        det = st.session_state.detection_data
        col1, col2 = st.columns([2, 1])
        with col1:
            if det.get('image_path') and os.path.exists(det['image_path']):
                st.image(det['image_path'], caption="AI View", use_container_width=True)
        with col2:
            st.write(f"### 🕳️ Potholes: {det['potholes']}")
            st.write(f"### ⚡ Cracks: {det['cracks']}")
            st.markdown("##### 📋 Data Summary")
            summary_df = pd.DataFrame({"Field": ["User", "Lat", "Lon", "Time"], "Value": [det.get('user_email', 'N/A'), str(det['lat']), str(det['lon']), det.get('timestamp', 'N/A')]})
            st.table(summary_df)

            if is_admin:
                if st.session_state.active_review:
                    if st.button("✅ Approve & Save", use_container_width=True, type="primary"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path, user_email) VALUES (?,?,?,?,?,?,?)", 
                                     (det['timestamp'], det['lat'], det['lon'], det['potholes'], det['cracks'], det['image_path'], det['user_email']))
                        conn.execute("DELETE FROM pending_reports WHERE id = ?", (st.session_state.active_index,))
                        conn.commit(); conn.close()
                        st.session_state.active_review = None; st.session_state.detection_data = None
                        st.rerun()
                    if st.button("🗑️ Discard", use_container_width=True):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM pending_reports WHERE id = ?", (st.session_state.active_index,))
                        conn.commit(); conn.close()
                        st.session_state.active_review = None; st.session_state.detection_data = None
                        st.rerun()
                else:
                    if st.button("💾 Save Directly", use_container_width=True):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path, user_email) VALUES (?,?,?,?,?,?,?)", 
                                     (det['timestamp'], det['lat'], det['lon'], det['potholes'], det['cracks'], det['image_path'], det['user_email']))
                        conn.commit(); conn.close()
                        st.success("Admin Data Saved!")

        st.markdown("---")
        st.subheader("📊 Damage Analysis Graph")
        chart_data = pd.DataFrame({"Count": [det['potholes'], det['cracks']]}, index=["Potholes", "Cracks"])
        st.bar_chart(chart_data)

        st.markdown("---")
        st.subheader("🗺️ Live Location Map")
        m = folium.Map(location=[det['lat'], det['lon']], zoom_start=15)
        folium.Marker([det['lat'], det['lon']], popup=f"Location").add_to(m)
        st_folium(m, width=1000, height=400)

# --- TAB 2: HISTORICAL DATA ---
with tab_hist:
    if is_admin:
        st.header("📂 Data Management & Records")
        st.info("ℹ️ Niche diye gaye drop-down list se report ka selection kre")
        
        report_type = st.selectbox(
            "Select Report Category",
            ["All Reports", "Crack", "Pothole", "user login"]
        )
        
        conn = sqlite3.connect(DB_NAME)
        
        # Function to display image from path
        def show_report_images(df):
            for index, row in df.iterrows():
                with st.expander(f"🖼️ View Image: Report ID {row.get('id', index)} (By: {row.get('user_email', 'N/A')})"):
                    img_path = row.get('image_path')
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, use_container_width=True)
                        st.write(f"📂 Path: {img_path}")
                    else:
                        st.error("❌ Image file not found on server.")

        if report_type == "All Reports":
            st.markdown("### 🕳️ Pothole Reports")
            df_potholes_all = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0 ORDER BY timestamp DESC", conn)
            st.dataframe(df_potholes_all, use_container_width=True)
            show_report_images(df_potholes_all)
            
            st.markdown("### ⚡ Crack Reports")
            df_cracks_all = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0 ORDER BY timestamp DESC", conn)
            st.dataframe(df_cracks_all, use_container_width=True)
            show_report_images(df_cracks_all)
            
            st.markdown("### 🔐 User Login Data")
            df_users_all = pd.read_sql_query("SELECT email, password FROM users", conn)
            st.dataframe(df_users_all, use_container_width=True)

        elif report_type == "Crack":
            st.subheader("⚡ Crack Data Only")
            df_cracks = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0", conn)
            st.dataframe(df_cracks, use_container_width=True)
            show_report_images(df_cracks)

        elif report_type == "Pothole":
            st.subheader("🕳️ Pothole Data Only")
            df_potholes = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0", conn)
            st.dataframe(df_potholes, use_container_width=True)
            show_report_images(df_potholes)

        elif report_type == "user login":
            st.subheader("👤 User Credentials")
            df_login = pd.read_sql_query("SELECT email, password FROM users", conn)
            st.dataframe(df_login, use_container_width=True)
            
        conn.close()
    else:
        st.warning("Admin access only.")
        
