import streamlit as st
from ultralytics import YOLO
from PIL import Image
import os
import datetime
import pandas as pd
import plotly.express as px
import requests
import json
import time

# ==========================================
# ⚙️ CONFIGURATION & CONSTANTS
# ==========================================
class Config:
    FIREBASE_API_KEY = st.secrets["FIREBASE_KEY"]
    
    MODEL_PATH = 'best.pt'
    UPLOAD_FOLDER = 'user_contributions'
    LOG_FILE = 'contribution_log.csv'
    GEOJSON_FILE = 'malaysia_states_v2.geojson'
    
    # Official State Names for Map Consistency
    ALL_STATES = [
        "Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", 
        "Pahang", "Perak", "Perlis", "Pulau Pinang", "Sabah", 
        "Sarawak", "Selangor", "Terengganu", 
        "W.P. Kuala Lumpur", "W.P. Putrajaya", "W.P. Labuan"
    ]

    # User Input -> Official Map Name Mapping
    STATE_MAPPING = {
        "Johor": "Johor", "Kedah": "Kedah", "Kelantan": "Kelantan", "Melaka": "Melaka",
        "Negeri Sembilan": "Negeri Sembilan", "Pahang": "Pahang", "Perak": "Perak",
        "Perlis": "Perlis", "Penang": "Pulau Pinang", "Sabah": "Sabah", "Sarawak": "Sarawak",
        "Selangor": "Selangor", "Terengganu": "Terengganu",
        "Kuala Lumpur": "W.P. Kuala Lumpur", "Putrajaya": "W.P. Putrajaya", "Labuan": "W.P. Labuan"
    }

# Ensure directories exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


# ==========================================
# 🔐 AUTHENTICATION MANAGER
# ==========================================
class AuthManager:
    BASE_URL = "https://identitytoolkit.googleapis.com/v1/accounts"

    @staticmethod
    def _request(endpoint, email, password):
        url = f"{AuthManager.BASE_URL}:{endpoint}?key={Config.FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        try:
            r = requests.post(url, json=payload)
            if r.status_code == 200:
                return r.json()['email'], None
            return None, r.json().get('error', {}).get('message', 'Unknown Error')
        except Exception as e:
            return None, str(e)

    @staticmethod
    def login(email, password):
        user, error = AuthManager._request("signInWithPassword", email, password)
        return user

    @staticmethod
    def register(email, password):
        return AuthManager._request("signUp", email, password)


# ==========================================
# 🗺️ MAP & DATA MANAGER
# ==========================================
class MapManager:
    @staticmethod
    @st.cache_resource
    def get_geojson():
        if os.path.exists(Config.GEOJSON_FILE):
            with open(Config.GEOJSON_FILE, "r") as f: return json.load(f)
        
        urls = [
            "https://raw.githubusercontent.com/mptwaktusolat/jakim.geojson/master/malaysia.state.geojson",
            "https://raw.githubusercontent.com/ynshung/malaysia-geojson/master/malaysia.state.geojson"
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    with open(Config.GEOJSON_FILE, "w") as f: json.dump(data, f)
                    return data
            except: continue
        return None

    @staticmethod
    def get_heatmap_fig(df_counts):
        geojson = MapManager.get_geojson()
        if not geojson: return None

        # Prepare full dataset (filling zeros for empty states)
        full_data = pd.DataFrame({'state': Config.ALL_STATES})
        if not df_counts.empty:
            counts = df_counts['state'].value_counts()
            full_data['count'] = full_data['state'].map(counts).fillna(0)
        else:
            full_data['count'] = 0

        fig = px.choropleth(
            full_data,
            geojson=geojson,
            locations="state",
            featureidkey="properties.name",
            color="count",
            color_continuous_scale="Greens",
            range_color=(0, full_data['count'].max() + 1),
            fitbounds="locations",
            basemap_visible=False
        )
        fig.update_layout(
            margin={"r":0,"t":0,"l":0,"b":0},
            geo=dict(bgcolor='rgba(0,0,0,0)')
        )
        return fig

class DataManager:
    @staticmethod
    def log_contribution(state_common_name):
        official = Config.STATE_MAPPING.get(state_common_name, state_common_name)
        new_data = pd.DataFrame({'state': [official]})
        
        header = not os.path.exists(Config.LOG_FILE)
        new_data.to_csv(Config.LOG_FILE, mode='a', header=header, index=False)

    @staticmethod
    def get_data():
        if os.path.exists(Config.LOG_FILE):
            return pd.read_csv(Config.LOG_FILE)
        return pd.DataFrame(columns=['state'])


# ==========================================
# 🖥️ UI COMPONENTS
# ==========================================
def render_login_screen():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🇲🇾 Malaysian Trash Annotation</h1>", unsafe_allow_html=True)
        st.info("Main Portal for MTA. Please identify yourself.")
        
        tab_login, tab_register = st.tabs(["🔑 Login", "📝 Register"])

        with tab_login:
            with st.form("login"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True):
                    user = AuthManager.login(email, password)
                    if user:
                        st.success("Welcome back!")
                        st.session_state.user = user
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")

        with tab_register:
            st.write("Join the team! Create your account below.")
            st.info("🛡️ Security Tip: Do not use your main email/banking password. Create a new password for this.")
            with st.form("register"):
                new_email = st.text_input("New Email")
                new_pass = st.text_input("New Password (Min 6 chars)", type="password")
                confirm_pass = st.text_input("Confirm Password", type="password")
                
                if st.form_submit_button("Create Account", use_container_width=True):
                    if new_pass != confirm_pass: st.warning("⚠️ Passwords differ!")
                    elif len(new_pass) < 6: st.warning("⚠️ Password too short.")
                    else:
                        user, err = AuthManager.register(new_email, new_pass)
                        if user:
                            st.success(f"✅ Created! Logging in...")
                            st.session_state.user = user
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Error: {err}")

def render_sidebar():
    with st.sidebar:
        st.write(f"🟢 **{st.session_state.user}**")
        if st.button("Sign Out"):
            st.session_state.user = None
            st.rerun()
        st.divider()
        df = DataManager.get_data()
        st.metric("Total Datapoints", len(df))

def render_main_app():
    st.title("🇲🇾 MTA Initiative")
    tab1, tab2, tab3 = st.tabs(["🗺️ National Heatmap", "📤 Contribute", "🤖 AI Demo"])

    # --- TAB 1: HEATMAP ---
    with tab1:
        st.subheader("National Coverage")
        df = DataManager.get_data()
        fig = MapManager.get_heatmap_fig(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("⚠️ Map data unavailable.")

    # --- TAB 2: CONTRIBUTE ---
    with tab2:
        col1, col2 = st.columns([1, 2], gap="large")
        with col1:
            st.error("⛔ CONTENT POLICY")
            st.markdown("""
            * ❌ **Nudity / NSFW**
            * ❌ **Sensitive Material: Containing religious symbols, political banners, or racially offensive material.**
            * ❌ **Clear faces, vehicle license plates, or private home interiors.**
            *License: CC-BY 4.0 Open Source*
            """)
        
        with col2:
            with st.form("sub", clear_on_submit=True):
                st.write("**Upload Details**")
                f = st.file_uploader("Photo", type=['jpg','png'])
                loc = st.selectbox("Location", list(Config.STATE_MAPPING.keys()))
                agree = st.checkbox("I confirm this image follows the Content Policy.")
                
                if st.form_submit_button("Submit"):
                    if not f or not agree:
                        st.warning("⚠️ File and Agreement required.")
                    else:
                        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M")
                        safe_user = st.session_state.user.replace("@","_").replace(".","_")
                        fn = f"{ts}_{safe_user}_{loc}.jpg"
                        
                        Image.open(f).save(os.path.join(Config.UPLOAD_FOLDER, fn))
                        DataManager.log_contribution(loc)
                        st.success("✅ Uploaded!")
                        st.balloons()

    # --- TAB 3: AI DEMO ---
    with tab3:
        st.subheader("Live AI Inference")
        st.warning("""Upload an image to see the YOLO model in action\n
                Model: YOLOv11-seg | Dataset: v5, build 11122025""")
        @st.cache_resource
        def get_model():
            return YOLO(Config.MODEL_PATH) if os.path.exists(Config.MODEL_PATH) else None
        
        model = get_model()
        if model:
            f = st.file_uploader("Test Image", key="ai_test")
            if f:
                res = model(Image.open(f))[0].plot()[...,::-1]
                st.image(res, caption="Detection Result")
        else:
            st.warning(f"⚠️ Model not found at `{Config.MODEL_PATH}`")


# ==========================================
# 🚀 MAIN ENTRY POINT
# ==========================================
def main():
    st.set_page_config(page_title="Malaysian Trash Annotation", page_icon="🇲🇾", layout="wide")
    
    if 'user' not in st.session_state:
        st.session_state.user = None

    if not st.session_state.user:
        render_login_screen()
    else:
        render_sidebar()
        render_main_app()

if __name__ == "__main__":
    main()