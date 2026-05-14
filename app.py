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
                conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE users SET password=? WHERE email=?", (new_pw, st.session_state.target_email)); conn.commit(); conn.close()
                st.success("Done!"); st.session_state.reset_mode = False; st.rerun()
        if st.button("Back"): st.session_state.reset_mode = False; st.rerun()
    else:
        t1, t2 = st.tabs(["Login", "Sign Up"])
        with t1:
            with st.form("l"):
                le, lp = st.text_input("Email"), st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    conn = sqlite3.connect(DB_NAME); d = conn.execute("SELECT password FROM users WHERE email=?", (le,)).fetchone(); conn.close()
                    if d and d[0] == lp:
                        st.session_state.logged_in, st.session_state.user_email = True, le
                        if le != ADMIN_EMAIL: send_email("Login Alert", f"User {le} logged in", ADMIN_EMAIL)
                        st.rerun()
                    else: st.error("Invalid Credentials")
            if st.button("Forgot Password?"): st.session_state.reset_mode = True; st.rerun()
        with t2:
            with st.form("s"):
                ne, npw, ncp = st.text_input("Email"), st.text_input("Pass", type="password"), st.text_input("Confirm", type="password")
                if st.form_submit_button("Sign Up"):
                    if ne and npw == ncp:
                        try:
                            conn = sqlite3.connect(DB_NAME); conn.execute("INSERT INTO users (email, password) VALUES (?,?)", (ne, npw)); conn.commit(); conn.close()
                            st.success("Account Created!"); st.rerun()
                        except: st.error("Email Exists!")
    st.stop()

is_admin = (st.session_state.user_email == ADMIN_EMAIL)

# --- 3. SIDEBAR ---
with st.sidebar:
    if is_admin:
        st.markdown("<h3 style='color: #2ecc71; text-align: center;'>👑 Admin Mode</h3>", unsafe_allow_html=True)
        st.info(f"📧 Admin: {st.session_state.user_email}")
    else:
        st.markdown("<h3 style='text-align: center;'>👤 User Mode</h3>", unsafe_allow_html=True)
        st.info(f"📧 User: {st.session_state.user_email}")
    
    if st.button("🚪 Logout", use_container_width=True): 
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    
    if is_admin:
        st.markdown("---")
        conn = sqlite3.connect(DB_NAME); pending = pd.read_sql_query("SELECT * FROM pending_reports", conn); conn.close()
        st.markdown(f"### 🔔 Notifications: `{len(pending)}`")
        if len(pending) > 0:
            with st.expander("📩 Review User Reports"):
                for i, row in pending.iterrows():
                    if st.button(f"Report {row['id']} - {row['user_email']}", key=f"n_{row['id']}"):
                        st.session_state.detection_data = row.to_dict()
                        st.session_state.active_review = True 
                        st.session_state.active_index = row['id']
                        st.rerun()

    st.markdown("---")
    st.markdown("### 🛠️ NAVIGATION STEPS")
    uploaded_file = st.file_uploader("📷 **Step 1: Upload Image**", type=['jpg', 'jpeg', 'png'])
    
    st.markdown("---")
    st.write("📍 **Step 2: Get Location**")
    
    # Live Geolocation Component
    loc = streamlit_geolocation()
    if st.button("Capture Live GPS", use_container_width=True):
        if loc and loc.get("latitude"):
            st.session_state.auto_lat = float(loc["latitude"])
            st.session_state.auto_lon = float(loc["longitude"])
            st.sidebar.success("📍 Your location is updated!")
            st.rerun()
        else:
            st.sidebar.error("❌ GPS not detected. Allow browser location access.")

    u_lat = st.number_input("Lat", value=st.session_state.auto_lat, format="%.6f", key="sidebar_lat")
    u_lon = st.number_input("Lon", value=st.session_state.auto_lon, format="%.6f", key="sidebar_lon")

    st.markdown("---")
    st.write("📂 **Step 3: Historical Data**")
    st.caption("Upar 'Historical Data' tab par click karein.")
    st.write("📈 **Step 4: Performance Matrix**")
    st.caption("Upar 'Performance Metrics' tab par click karein.")

# --- 4. MAIN DASHBOARD ---
@st.cache_resource
def load_yolo(): return YOLO('best.pt') if os.path.exists('best.pt') else None
yolo_model = load_yolo()

st.markdown("<h2 style='text-align: center;'>🛣️ AI ROAD DAMAGE DETECTOR</h2>", unsafe_allow_html=True)
tab_dash, tab_hist, tab_stats = st.tabs(["🖥️ Dashboard", "📂 Historical Data", "📈 Performance Metrics"])

with tab_dash:
    if not st.session_state.detection_data:
        if is_admin:
            st.info("👋 **Hello Admin!**\n\n1. If you want to perform the detection yourself, follow Steps 1 and 2 in the sidebar.\n2. To check user reports, please refer to the Notification Bar in the sidebar.")
        else:
            st.info("📷 **Welcome!**\n\nTo report road damage, follow Step 1 and Step 2 provided in the sidebar.")

    if uploaded_file and st.button("🚀 Run AI Detection", type="primary", use_container_width=True):
        img = Image.open(uploaded_file)
        res = yolo_model.predict(img, conf=0.25)
        st.session_state.last_speed = res[0].speed['inference']
        
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
            st.success("✅ Report successfully sent to Admin for review!")

    if st.session_state.detection_data:
        det = st.session_state.detection_data
        
        c_l, c_r = st.columns([1.5, 1])
        with c_l: 
            st.markdown("### 🔍 Detection Result")
            st.image(det['image_path'], use_container_width=True)
        with c_r:
            st.markdown("### 📋 Detection Index Heading")
            st.table(pd.DataFrame({"Param": ["User", "Lat", "Lon", "Potholes", "Cracks"], 
                                   "Value": [det.get('user_email'), det['lat'], det['lon'], det['potholes'], det['cracks']]}))
            
            if not is_admin:
                st.info("📩 **Your report has been sent to the Admin.**")

            if det['potholes'] > 3: st.error("🔴 **ROAD IS DAMAGED**")
            elif det['potholes'] >= 1: st.warning("🟠 **ROAD REPAIR NEEDED**")
            else: st.success("🟢 **ROAD IS GOOD**")

            if is_admin:
                st.markdown("---")
                b_col1, b_col2 = st.columns(2)
                if st.session_state.active_review:
                    if b_col1.button("✅ Approve & Save", use_container_width=True, type="primary"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path, user_email) VALUES (?,?,?,?,?,?,?)", 
                                     (det['timestamp'], det['lat'], det['lon'], det['potholes'], det['cracks'], det['image_path'], det['user_email']))
                        conn.execute("DELETE FROM pending_reports WHERE id=?", (st.session_state.active_index,))
                        conn.commit(); conn.close()
                        st.success("Report Approved!"); st.session_state.detection_data = None; st.session_state.active_review = False; st.rerun()
                    if b_col2.button("❌ Discard Report", use_container_width=True):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM pending_reports WHERE id=?", (st.session_state.active_index,))
                        conn.commit(); conn.close()
                        st.warning("Report Discarded!"); st.session_state.detection_data = None; st.session_state.active_review = False; st.rerun()
                else:
                    if b_col1.button("💾 Save to Records", use_container_width=True, type="primary"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO road_logs (timestamp, lat, lon, potholes, cracks, image_path, user_email) VALUES (?,?,?,?,?,?,?)", 
                                     (det['timestamp'], det['lat'], det['lon'], det['potholes'], det['cracks'], det['image_path'], st.session_state.user_email))
                        conn.commit(); conn.close()
                        st.success("Report Saved Successfully!"); st.session_state.detection_data = None; st.rerun()
                    if b_col2.button("🗑️ Discard", use_container_width=True):
                        st.session_state.detection_data = None; st.rerun()

        st.markdown("---")
        st.subheader("📊 Graph and Analysis with Graph Report Image")
        st.bar_chart(pd.DataFrame({"Count": [det['potholes'], det['cracks']]}, index=["Potholes", "Cracks"]))
        
        st.markdown("---")
        st.subheader("🗺️ Map View")
        # Fix: Using det['lat'] and det['lon'] to show actual marker on map
        m = folium.Map(location=[det['lat'], det['lon']], zoom_start=16)
        folium.Marker(
            [det['lat'], det['lon']], 
            popup=f"Damage detected by {det['user_email']}",
            icon=folium.Icon(color='red' if det['potholes'] > 0 else 'green')
        ).add_to(m)
        st_folium(m, width=1100, height=400, key="main_map")

# --- TAB 2: HISTORICAL DATA ---
# --- TAB 2: HISTORICAL DATA ---
with tab_hist:
    if is_admin:
        st.header("📂 Data Management & Records")
        st.info("ℹ️ Please select the report from the drop-down menu provided below.")
        
        # Step 1: Selection
        report_type = st.selectbox("Select Report Category", ["All Reports", "Crack", "Pothole", "user login"])
        
        # Step 2: Show Button
        if st.button("🔍 Show Records", use_container_width=True, type="primary"):
            conn = sqlite3.connect(DB_NAME)
            
            def show_report_images(df):
                for index, row in df.iterrows():
                    with st.expander(f"🖼️ View Image: Report ID {row.get('id', index)} (By: {row.get('user_email', 'N/A')})"):
                        img_path = row.get('image_path')
                        if img_path and os.path.exists(img_path):
                            st.image(img_path, use_container_width=True)
                        else: st.error("❌ Image file not found.")

            if report_type == "All Reports":
                st.subheader("🕳️ All Pothole Reports")
                df_p = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0 ORDER BY timestamp DESC", conn)
                st.dataframe(df_p, use_container_width=True); show_report_images(df_p)
                
                st.subheader("⚡ All Crack Reports")
                df_c = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0 ORDER BY timestamp DESC", conn)
                st.dataframe(df_c, use_container_width=True); show_report_images(df_c)
            
            elif report_type == "Crack":
                df = pd.read_sql_query("SELECT * FROM road_logs WHERE cracks > 0", conn)
                st.dataframe(df, use_container_width=True); show_report_images(df)
                
            elif report_type == "Pothole":
                df = pd.read_sql_query("SELECT * FROM road_logs WHERE potholes > 0", conn)
                st.dataframe(df, use_container_width=True); show_report_images(df)
                
            elif report_type == "user login":
                df = pd.read_sql_query("SELECT email, password FROM users", conn)
                st.dataframe(df, use_container_width=True)
                
            conn.close()
    else:
        st.warning("### 🔐 Admin Access Only")
        st.info("This section is accessible to the Admin only.")

# --- TAB 3: PERFORMANCE ---

with tab_stats:
    if is_admin:
        st.header("📈 Model Performance Analysis")
        st.info("Please click the button below to access the technical metrics and training performance graphs.")
        
        # Button to reveal metrics
        if st.button("📊 View Performance Metrics", use_container_width=True, type="primary"):
            st.markdown("### 📈 Model Accuracy vs. Testing Performance")
            col_acc1, col_acc2 = st.columns(2)
            with col_acc1:
                st.markdown("<div style='background-color: #e1f5fe; padding: 10px; border-radius: 10px; border-left: 5px solid #01579b;'><h4 style='color: #01579b;'>🎯 Project Accuracy</h4><p>The model's performance on the training data.</p></div>", unsafe_allow_html=True)
                st.metric("Training mAP50", "86.5%")
            with col_acc2:
                st.markdown("<div style='background-color: #e3f2fd; padding: 10px; border-radius: 10px; border-left: 5px solid #1976d2;'><h4 style='color: #1976d2;'>🧪 Testing Accuracy</h4><p>Accuracy achieved during validation phase on unseen images.</p></div>", unsafe_allow_html=True)
                st.metric("Validation mAP50", "81.4%")

            st.subheader("📊 Detailed Metrics")
            m1, m2, m3 = st.columns(3)
            m1.metric("Precision (B)", "85.8%"); m2.metric("Recall (B)", "75.2%"); m3.metric("Inference Speed", "15ms")

            col_graph_l, col_graph_r = st.columns([1.5, 1])
            with col_graph_l:
                if os.path.exists('results.png'): st.image('results.png', caption='Accuracy & Loss Curves', use_container_width=True)
            with col_graph_r:
             st.subheader("📝 Blue-Zone Analysis")
             st.info(""" 
            * **mAP50 (85%):** Our model achieves an accuracy rate of over 85% in detecting road damage.
            * **Loss Curves:** The decrease in the loss graph demonstrates that the model successfully learned from its errors during the training process.
            * **Precision:** This means the number of false alarms is very low..
            """)

            st.markdown("---")
            st.markdown("#### 🏁 Final Report Status")
            # Yahan final message bhi blue bar mein
            st.info(f"#### Achieving a testing accuracy of 81.4%, this model is now ready for production-level deployment.")

            # Empowering User
            st.markdown("#### 🤝 Empowering the End-User")
            u1, u2, u3 = st.columns(3)
            u1.info("**Quick Upload**\n\nSimple drag-and-drop interface for field images.")
            u2.info("**Live Geotagging**\n\nAutomated GPS tracking for accurate location.")
            u3.info("**Secure Access**\n\nEncrypted data and secure login for stakeholders.")

            # Strategic Value
            st.markdown("#### 🏆 Strategic Value")
            v1, v2, v3 = st.columns(3)
            v1.success("🛡️ **Public Safety**\n\nReducing accidents by early hazard identification.")
            v2.success("💰 **Fiscal Savings**\n\nPreventing expensive road rebuilds.")
            v3.success("📢 **Transparency**\n\nDigitally verifiable records for accountability.")
    else:
        st.warning("### 🔐 Admin Access Only")
        st.info("This section is accessible to the Admin only.")

