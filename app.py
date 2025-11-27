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
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_scope' not in st.session_state:
    st.session_state.user_scope = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False # Default to Light Mode

# --- DYNAMIC THEME STYLING (Ultra High Contrast) ---
def apply_theme(is_dark):
    """
    Injects CSS to override the interface colors based on the toggle.
    """
    if is_dark:
        # DARK MODE COLORS
        bg_color = "#0e1117"           # Standard Dark Background
        sidebar_bg = "#262730"         # Standard Sidebar
        text_color = "#ffffff"         # White Text
        
        # CARD / METRIC COLORS
        metric_bg = "#1e1e1e"          
        metric_border = "#606060"      # Lighter Grey Border for visibility
        
        # INPUT FIELDS ( The Key Fix )
        input_bg = "#000000"           # Pure Black Input Background (High Contrast)
        input_border = "#ffffff"       # White Border
        input_text = "#ffffff"         
        
        # INFO BOX (Blue Box Fix)
        info_box_bg = "#1c2e4a"        # Dark Blue Background
        info_box_text = "#d1e3ff"      # Very Light Blue Text
        
    else:
        # LIGHT MODE COLORS
        bg_color = "#ffffff"
        sidebar_bg = "#f0f2f6"
        text_color = "#000000"
        metric_bg = "#ffffff"
        metric_border = "#dcdcdc"
        input_bg = "#ffffff"
        input_border = "#dcdcdc"
        input_text = "#000000"
        info_box_bg = "#e8f0fe"
        info_box_text = "#0e1117"

    st.markdown(f"""
        <style>
            /* 1. Global App Background & Text */
            .stApp {{
                background-color: {bg_color};
                color: {text_color};
            }}
            
            /* 2. Sidebar Styling */
            section[data-testid="stSidebar"] {{
                background-color: {sidebar_bg};
                border-right: 1px solid {metric_border};
            }}
            
            /* 3. INPUT FIELDS - High Contrast Fix */
            /* Target Text Inputs and Number Inputs */
            .stTextInput input, .stNumberInput input {{
                background-color: {input_bg} !important;
                color: {input_text} !important;
                border: 1px solid {input_border} !important;
                border-radius: 5px;
            }}
            
            /* Target Select Boxes (Dropdowns) */
            div[data-baseweb="select"] > div {{
                background-color: {input_bg} !important;
                color: {input_text} !important;
                border: 1px solid {input_border} !important;
            }}
            /* Fix Text inside Dropdowns */
            div[data-baseweb="select"] span {{
                color: {input_text} !important;
            }}
            
            /* 4. INFO BOX FIX (User: admin box) */
            div[data-testid="stAlert"] {{
                background-color: {info_box_bg};
                color: {info_box_text};
                border: 1px solid {info_box_text};
            }}
            div[data-testid="stAlert"] p {{
                color: {info_box_text} !important;
            }}

            /* 5. Metric Cards */
            div[data-testid="stMetric"] {{
                background-color: {metric_bg};
                border: 1px solid {metric_border};
                box-shadow: 0 2px 4px rgba(0,0,0,0.5);
            }}
            div[data-testid="stMetric"] label {{
                color: {text_color} !important;
            }}
            
            /* 6. Headers */
            h1, h2, h3, h4, h5, h6 {{
                color: {text_color} !important;
            }}
            
            /* 7. Remove Default Header/Footer */
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header {{visibility: hidden;}}
        </style>
    """, unsafe_allow_html=True)


# --- AUTHENTICATION FLOW ---
if not st.session_state.logged_in:
    # Apply standard light theme for login screen for consistency
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
                st.session_state.user_scope = user[3] # user[3] is the SCOPE
                st.rerun()
            else:
                st.error("Invalid Credentials")

else:
    # --- MAIN APP LAYOUT ---
    
    # 1. Sidebar Header
    st.sidebar.title("📦 SCOO Assets")
    
    # --- NEW: VERSION BANNER ---
    st.sidebar.markdown(
        f"""
        <div style="background-color: #262730; border: 1px solid #444; border-radius: 5px; padding: 5px 10px; margin-bottom: 20px; text-align: center;">
            <span style="color: #888; font-size: 0.8em;">VERSION</span><br>
            <span style="color: #fff; font-weight: bold;">{config.APP_VERSION}</span>
        </div>
        """, 
        unsafe_allow_html=True
    )
    # ---------------------------
    
    st.sidebar.info(f"User: **{st.session_state.username}**\nAccess: **{st.session_state.user_scope}**")
    
    # 2. Theme Toggle (Added Here)
    st.sidebar.divider()
    # We use a callback to rerun the app immediately when toggled
    def toggle_theme():
        st.session_state.dark_mode = not st.session_state.dark_mode

    st.sidebar.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, on_change=toggle_theme)
    
    # Apply the selected theme
    apply_theme(st.session_state.dark_mode)

    # 3. Navigation Menu
    options = ["Dashboard", "Add Asset", "Inventory"]
    
    if st.session_state.user_scope == config.SCOPE_ADMIN:
        options.append("Admin")
        
    choice = st.sidebar.radio("Navigation", options)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Logout", type="secondary"):
        st.session_state.logged_in = False
        st.session_state.user_scope = None
        st.rerun()

    # Router
    if choice == "Dashboard":
        views.show_dashboard(db, st.session_state.user_scope)
    elif choice == "Add Asset":
        views.show_add_asset(db, st.session_state.user_scope)
    elif choice == "Inventory":
        views.show_inventory(db, st.session_state.user_scope)
    elif choice == "Admin":
        views.show_admin(db, st.session_state.user_scope)