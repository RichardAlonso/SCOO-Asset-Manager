import streamlit as st
from database import Database
import views
import config

# Page Configuration
st.set_page_config(
    page_title="SCOO Asset Manager",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Database
db = Database()

# --- SESSION STATE MANAGEMENT ---
if 'page' not in st.session_state: st.session_state.page = 0
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_scope' not in st.session_state: st.session_state.user_scope = None
if 'username' not in st.session_state: st.session_state.username = None
if 'dark_mode' not in st.session_state: st.session_state.dark_mode = False 

# --- DYNAMIC THEME STYLING ---
def get_css(is_dark):
    if is_dark:
        bg_color, sidebar_bg, text_color = "#0e1117", "#262730", "#ffffff"
        metric_bg, metric_border = "#1e1e1e", "#606060"
        input_bg, input_border, input_text = "#000000", "#ffffff", "#ffffff"
        info_box_bg, info_box_text = "#1c2e4a", "#d1e3ff"
    else:
        bg_color, sidebar_bg, text_color = "#ffffff", "#f0f2f6", "#000000"
        metric_bg, metric_border = "#ffffff", "#dcdcdc"
        input_bg, input_border, input_text = "#ffffff", "#dcdcdc", "#000000"
        info_box_bg, info_box_text = "#e8f0fe", "#0e1117"

    return f"""
        <style>
            .stApp {{ background-color: {bg_color}; color: {text_color}; }}
            section[data-testid="stSidebar"] {{ background-color: {sidebar_bg}; border-right: 1px solid {metric_border}; }}
            
            .stTextInput input, .stNumberInput input {{ background-color: {input_bg} !important; color: {input_text} !important; border: 1px solid {input_border} !important; border-radius: 5px; }}
            div[data-baseweb="select"] > div {{ background-color: {input_bg} !important; color: {input_text} !important; border: 1px solid {input_border} !important; }}
            div[data-baseweb="select"] span {{ color: {input_text} !important; }}
            
            div[data-testid="stAlert"] {{ background-color: {info_box_bg}; color: {info_box_text}; border: 1px solid {info_box_text}; }}
            div[data-testid="stAlert"] p {{ color: {info_box_text} !important; }}

            div[data-testid="stMetric"] {{ background-color: {metric_bg}; border: 1px solid {metric_border}; box-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
            div[data-testid="stMetric"] label {{ color: {text_color} !important; }}
            
            h1, h2, h3, h4, h5, h6 {{ color: {text_color} !important; }}
            footer {{visibility: hidden;}}
        </style>
    """

def apply_theme(is_dark):
    st.markdown(get_css(is_dark), unsafe_allow_html=True)

# --- AUTHENTICATION FLOW ---
if not st.session_state.logged_in:
    apply_theme(False)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.header("SCOO Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary", use_container_width=True):
            user = db.verify_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.session_state.user_scope = user[3]
                st.rerun()
            else:
                st.error("Invalid Credentials")
else:
    # --- MAIN APP LAYOUT ---
    st.sidebar.title("📦 SCOO Assets")
    st.sidebar.markdown(f"""
        <div style="background-color: #262730; border: 1px solid #444; border-radius: 5px; padding: 5px 10px; margin-bottom: 20px; text-align: center;">
            <span style="color: #888; font-size: 0.8em;">VERSION</span><br>
            <span style="color: #fff; font-weight: bold;">{config.APP_VERSION}</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.sidebar.info(f"User: **{st.session_state.username}**\nAccess: **{st.session_state.user_scope}**")
    st.sidebar.divider()
    
    def toggle_theme(): st.session_state.dark_mode = not st.session_state.dark_mode
    st.sidebar.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, on_change=toggle_theme)
    apply_theme(st.session_state.dark_mode)

    options = ["Dashboard", "Add Asset", "Inventory"]
    if st.session_state.user_scope == config.SCOPE_ADMIN: options.append("Admin")
        
    choice = st.sidebar.radio("Navigation", options)
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Logout", type="secondary"):
        st.session_state.logged_in = False
        st.session_state.user_scope = None
        st.rerun()

    if choice == "Dashboard": views.show_dashboard(db, st.session_state.user_scope)
    elif choice == "Add Asset": views.show_add_asset(db, st.session_state.user_scope)
    elif choice == "Inventory": views.show_inventory(db, st.session_state.user_scope)
    elif choice == "Admin": views.show_admin(db, st.session_state.user_scope)