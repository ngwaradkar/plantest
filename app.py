import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import matplotlib.pyplot as plt
import importlib
import data_loader as dl
importlib.reload(dl)
import allocation_engine as ae
importlib.reload(ae)

# Initialize session state for theme preference from database
db_theme = '☀️ White Theme'
try:
    db_theme = dl.load_metadata('theme', '☀️ White Theme')
except Exception:
    pass

if 'theme' not in st.session_state:
    st.session_state.theme = db_theme

# Set page config
st.set_page_config(
    page_title="TCF1 & TCF2 VIN generation PPC Dashboard",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Render theme selector at top right
col_title_card, col_theme_select = st.columns([5.5, 1])
with col_theme_select:
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    theme_option = st.selectbox(
        "🎨 Interface Theme",
        options=["☀️ White Theme", "🌙 Dark Theme"],
        index=0 if st.session_state.theme == '☀️ White Theme' else 1,
        key="theme_selection_key"
    )
    if theme_option != st.session_state.theme:
        st.session_state.theme = theme_option
        try:
            dl.save_metadata('theme', theme_option)
        except Exception:
            pass
        st.rerun()

is_dark = st.session_state.theme == "🌙 Dark Theme"

# Inject style blocks dynamically using CSS variables
if is_dark:
    theme_vars = """
    :root {
        --bg-primary: #0E1117;
        --bg-secondary: #1F2937;
        --card-bg: #161B22;
        --text-primary: #FAFAFA;
        --text-secondary: #D1D5DB;
        --border-color: #30363D;
        --accent-color: #4A9EFF;
        --accent-hover: #7BB4FF;
        --success-color: #10B981;
        --warning-color: #F59E0B;
        --danger-color: #EF4444;
        --hover-tint: rgba(74, 158, 255, 0.08);
        --card-ready-bg: #064E3B;
        --card-ready-text: #D1FAE5;
        --card-blocked-bg: #7F1D1D;
        --card-blocked-text: #FEE2E2;
        
        /* Map Streamlit native properties to match */
        --primary-color: var(--accent-color) !important;
        --background-color: var(--bg-primary) !important;
        --secondary-background-color: var(--bg-secondary) !important;
        --text-color: var(--text-primary) !important;
    }
    """
else:
    theme_vars = """
    :root {
        --bg-primary: #F9FAFB;
        --bg-secondary: #FFFFFF;
        --card-bg: #FFFFFF;
        --text-primary: #111827;
        --text-secondary: #374151;
        --border-color: #E5E7EB;
        --accent-color: #1D4ED8;
        --accent-hover: #1E3A8A;
        --success-color: #16A34A;
        --warning-color: #F59E0B;
        --danger-color: #DC2626;
        --hover-tint: rgba(29, 78, 216, 0.05);
        --card-ready-bg: #F0FAF4;
        --card-ready-text: #166534;
        --card-blocked-bg: #FFF5F5;
        --card-blocked-text: #B91C1C;
        
        /* Map Streamlit native properties to match */
        --primary-color: var(--accent-color) !important;
        --background-color: var(--bg-primary) !important;
        --secondary-background-color: var(--bg-secondary) !important;
        --text-color: var(--text-primary) !important;
    }
    """

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    {theme_vars}
    
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif !important;
    }}
    
    /* Global App Background */
    .stApp {{
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }}
    
    /* Completely hide sidebar and collapse button */
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {{
        display: none !important;
        width: 0px !important;
    }}
    [data-testid="collapsedControl"] {{
        display: none !important;
    }}
    .stApp [data-testid="stHeader"] {{
        left: 0px !important;
        background-color: transparent !important;
    }}
    .main .block-container {{
        padding: 2.5rem 3rem !important;
        max-width: 100% !important;
    }}
    
    /* Premium Metric Cards with Hover lift animation */
    div[data-testid="stMetric"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--border-color) !important;
        padding: 1rem 1.25rem !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        min-width: 0 !important;
        width: 100% !important;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-4px) !important;
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08) !important;
        border-color: var(--accent-hover) !important;
    }}
    
    /* Colorful left border accents for each metric column */
    div[data-testid="column"]:nth-of-type(1) div[data-testid="stMetric"] {{
        border-left: 5px solid var(--accent-color) !important;
    }}
    div[data-testid="column"]:nth-of-type(2) div[data-testid="stMetric"] {{
        border-left: 5px solid #06B6D4 !important; /* Cyan */
    }}
    div[data-testid="column"]:nth-of-type(3) div[data-testid="stMetric"] {{
        border-left: 5px solid var(--success-color) !important; /* Success Green */
    }}
    div[data-testid="column"]:nth-of-type(4) div[data-testid="stMetric"] {{
        border-left: 5px solid var(--danger-color) !important; /* Danger Red */
    }}
    
    div[data-testid="stMetric"] label {{
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
    }}
    
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
        color: var(--text-primary) !important;
        font-weight: 750 !important;
        font-size: 1.15rem !important;
        line-height: 1.3 !important;
        letter-spacing: -0.015em !important;
        word-break: normal !important;
        white-space: normal !important;
        overflow: visible !important;
    }}
    
    /* Segmented control for tabs */
    div[data-baseweb="tab-list"] {{
        background-color: var(--bg-secondary) !important;
        padding: 0.3rem !important;
        border-radius: 12px !important;
        gap: 6px !important;
        margin-bottom: 2rem !important;
        border: 1px solid var(--border-color) !important;
    }}
    button[data-baseweb="tab"] {{
        background-color: transparent !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.4rem !important;
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        transition: all 0.2s ease !important;
    }}
    button[data-baseweb="tab"]:hover {{
        color: var(--text-primary) !important;
        background-color: var(--hover-tint) !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        background-color: var(--card-bg) !important;
        color: var(--accent-color) !important;
        border: 1px solid var(--border-color) !important;
        border-bottom: 3px solid var(--accent-color) !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04) !important;
    }}
    div[data-baseweb="tab-border"] {{
        display: none !important;
    }}
    
    /* Expander styling */
    details[data-testid="stExpander"] {{
        background-color: var(--card-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.01) !important;
        margin-bottom: 1.5rem !important;
    }}
    details[data-testid="stExpander"] summary {{
        font-weight: 600 !important;
        color: var(--text-primary) !important;
    }}
    
    /* Form inputs and select boxes */
    div[data-baseweb="select"], div[data-baseweb="input"], input, textarea {{
        background-color: var(--card-bg) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-color) !important;
        border-radius: 10px !important;
    }}
    div[data-baseweb="select"]:hover, div[data-baseweb="input"]:hover {{
        border-color: var(--accent-color) !important;
    }}
    
    /* Button premium styling with micro-interaction hover/active states */
    button[kind="primary"] {{
        background-color: var(--accent-color) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.6rem !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}
    button[kind="primary"]:hover {{
        background-color: var(--accent-hover) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 16px rgba(37, 99, 235, 0.25) !important;
    }}
    button[kind="primary"]:active {{
        transform: translateY(0) !important;
    }}
    
    button[kind="secondary"] {{
        background-color: var(--card-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.6rem !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}
    button[kind="secondary"]:hover {{
        background-color: var(--hover-tint) !important;
        border-color: var(--accent-color) !important;
        transform: translateY(-2px) !important;
    }}
    button[kind="secondary"]:active {{
        transform: translateY(0) !important;
    }}
    
    /* Table / Dataframe premium look with soft shadow card mapping */
    div[data-testid="stDataFrame"] {{
        border-radius: 12px !important;
        border: 1px solid var(--border-color) !important;
        background-color: var(--card-bg) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02) !important;
        overflow: hidden !important;
    }}
    
    /* st.form container override */
    div[data-testid="stForm"] {{
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
        background-color: var(--card-bg) !important;
        padding: 1.5rem !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02) !important;
    }}
    
    /* Headings */
    h1, h2, h3, h4, h5, h6 {{
        font-family: 'Inter', sans-serif !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.02em !important;
        line-height: 1.3 !important;
    }}
    h1 {{ font-size: 2.2rem !important; font-weight: 850 !important; }}
    h2 {{ font-size: 1.8rem !important; font-weight: 750 !important; }}
    h3 {{ font-size: 1.45rem !important; font-weight: 700 !important; }}
    h4 {{ font-size: 1.2rem !important; font-weight: 650 !important; }}
    
    /* Horizontal rules */
    hr {{
        border-color: var(--border-color) !important;
    }}
    
    /* Custom file uploader border */
    section[data-testid="stFileUploader"] {{
        border: 2px dashed var(--border-color) !important;
        border-radius: 12px !important;
        background-color: var(--bg-secondary) !important;
    }}
</style>
""", unsafe_allow_html=True)

# Render the Title Card
with col_title_card:
    st.markdown("""
    <div style="background: linear-gradient(135deg, var(--accent-color) 0%, #06B6D4 100%); padding: 1.8rem 2.2rem; border-radius: 16px; margin-bottom: 2rem; color: white; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);">
        <h1 style="color: white !important; font-weight: 850; margin: 0; font-size: 2.2rem; letter-spacing: -0.03em; font-family: 'Inter', sans-serif;">TCF1 & TCF2 VIN Generation PPC Dashboard</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.05rem; font-weight: 400; font-family: 'Inter', sans-serif;">Painted Body Storage (PBS) Buffer Allocation & Multi-Stage Material Availability Summary</p>
    </div>
    """, unsafe_allow_html=True)

# ----------------- SESSION STATE & INITIALIZATION -----------------
import datetime

# Pre-populated Engine Stocks (Defaulting to 0 as requested)
engine_default_data = [
    {"TCF Line": "TCF1", "Engine Part No": "54850000PTP001", "Model": "Punch MT SA", "TA Code": "3302", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF1", "Engine Part No": "54850000PTP002", "Model": "Punch AMT SA", "TA Code": "3404", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF1", "Engine Part No": "54970000PTP002", "Model": "Punch TC MCE", "TA Code": "7349", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF1", "Engine Part No": "54970000PTP003", "Model": "Punch MCE MT", "TA Code": "3641", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF1", "Engine Part No": "54970000PTP004", "Model": "Punch MCE AMT", "TA Code": "3406", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF1", "Engine Part No": "54970000PTP005", "Model": "Punch MCE CNG MT", "TA Code": "3627", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF1", "Engine Part No": "54970000PTP031", "Model": "Punch MCE CNG AMT", "TA Code": "3403", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF1", "Engine Part No": "546816111212", "Model": "Nova", "TA Code": "5468", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF2", "Engine Part No": "572900000118", "Model": "Harrier / Safari Diesel AT", "TA Code": "—", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF2", "Engine Part No": "572900000120", "Model": "Harrier / Safari Diesel MT", "TA Code": "—", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF2", "Engine Part No": "54780000PTP001", "Model": "Harrier / Safari Petrol TGDI MT", "TA Code": "—", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF2", "Engine Part No": "54780000PTP002", "Model": "Harrier / Safari Petrol TGDI AT", "TA Code": "—", "Clearance After 6:30AM": 0},
    {"TCF Line": "TCF2", "Engine Part No": "547380400103", "Model": "Harrier EV", "TA Code": "5473", "Clearance After 6:30AM": 0}
]

# Load last reset time from database metadata
db_last_reset = None
try:
    db_last_reset = dl.load_metadata('last_reset_time')
except Exception:
    pass
now = datetime.datetime.now()
reset_threshold = now.replace(hour=6, minute=30, second=0, microsecond=0)

if 'last_reset_time' not in st.session_state:
    if db_last_reset:
        st.session_state.last_reset_time = datetime.datetime.fromisoformat(db_last_reset)
    else:
        st.session_state.last_reset_time = now
        try:
            dl.save_metadata('last_reset_time', now.isoformat())
        except Exception:
            pass

# Load engine stocks from DB or defaults
if 'engine_df' not in st.session_state:
    db_engine_df = None
    try:
        db_engine_df = dl.load_engine_stocks_from_db()
    except Exception:
        pass
    if db_engine_df is not None:
        st.session_state.engine_df = db_engine_df
    else:
        st.session_state.engine_df = pd.DataFrame(engine_default_data)

# If now has crossed 6:30 AM today, and last reset was before 6:30 AM today
if now >= reset_threshold and st.session_state.last_reset_time < reset_threshold:
    st.session_state.engine_df = pd.DataFrame(engine_default_data)
    try:
        dl.save_engine_stocks_to_db(st.session_state.engine_df)
    except Exception:
        pass
    st.session_state.last_reset_time = now
    try:
        dl.save_metadata('last_reset_time', now.isoformat())
    except Exception:
        pass
    st.toast("🔄 Shift start auto-reset triggered (6:30 AM). Starting stocks cleared.", icon="🔄")

# Load active directory selection from database metadata
db_data_source = 'Root Directory (Production)'
try:
    db_data_source = dl.load_metadata('data_source_dir', 'Root Directory (Production)')
except Exception:
    pass

if 'data_source_dir' not in st.session_state:
    st.session_state.data_source_dir = db_data_source

# Auto-detect file mappings in workspace
workspace_dir = os.path.dirname(os.path.abspath(__file__))

if st.session_state.data_source_dir == 'TEST Directory (Sample Data)':
    active_dir = os.path.join(workspace_dir, "TEST")
else:
    active_dir = workspace_dir

# Scan active folder for default files dynamically
detected_files = dl.detect_and_classify_files(active_dir)

all_categories = [
    'BOM', 'FLOAT_REPORT', 
    'TCF1_WIRING_STOCK', 'TCF2_WIRING_STOCK', 
    'TCF1_ALTROZ_COCKPIT_STOCK', 'TCF1_NOVA_COCKPIT_STOCK', 'TCF2_COCKPIT_STOCK',
    'TCF1_VGL', 'TCF2_VGL'
]

loaded_data = {}

# ----------------- CONTROL CENTER (UPLOADS & ENGINE STOCKS) -----------------
# We put the control panel in a clean main-body expander.
# The expander starts collapsed if the core files are already auto-loaded.
db_bom_exists = dl.load_bom_from_db() is not None
default_bom_path = detected_files.get('BOM')
default_float_path = detected_files.get('FLOAT_REPORT')
default_core_available = (db_bom_exists or default_bom_path is not None) and default_float_path is not None

config_expander = st.expander(
    "⚙️ Control Panel: File Uploads & Engine Starting Stocks (Click to Expand/Collapse)",
    expanded=not default_core_available
)

with config_expander:
    col_upload, col_engine = st.columns([1, 1.2])
    
    with col_upload:
        st.markdown("#### 📤 Upload Raw Plant Files")
        
        # Data source selector inside Control Panel
        dir_option = st.selectbox(
            "📁 Active Data Source Directory",
            options=["Root Directory (Production)", "TEST Directory (Sample Data)"],
            index=0 if st.session_state.data_source_dir == "Root Directory (Production)" else 1,
            key="data_source_dir_select",
            help="Select whether the dashboard should load data from the production Root folder or the TEST sample data folder."
        )
        if dir_option != st.session_state.data_source_dir:
            st.session_state.data_source_dir = dir_option
            try:
                dl.save_metadata('data_source_dir', dir_option)
            except Exception:
                pass
            st.rerun()
            
        uploaded_files = st.file_uploader(
            "Upload plant reports to replace existing ones",
            accept_multiple_files=True,
            help="Upload raw spreadsheets (Float, Wiring, Cockpit, or VGL). They will automatically replace older files on disk."
        )
        
        # Process uploads immediately, saving to session state buffers and optionally to disk
        uploaded_ids = [f"{f.name}_{f.size}" for f in uploaded_files] if uploaded_files else []
        last_processed_ids = st.session_state.get("last_processed_upload_ids", [])
        
        if not uploaded_files:
            st.session_state.last_processed_upload_ids = []
            
        if uploaded_files and uploaded_ids != last_processed_ids:
            uploaded_mappings = dl.classify_files(uploaded_files)
            replaced_any = False
            for category, uploaded_file in uploaded_mappings.items():
                st.session_state[f"buffer_{category}"] = uploaded_file
                
                if category == 'BOM':
                    try:
                        parsed_bom = dl.load_bom(uploaded_file)
                        try:
                            dl.save_bom_to_db(parsed_bom)
                            dl.save_metadata(f"uploaded_{category}", uploaded_file.name)
                        except Exception:
                            pass
                        st.toast("💾 Master BOM replaced!", icon="💾")
                        replaced_any = True
                    except Exception as e:
                        st.error(f"Failed to parse uploaded BOM: {e}")
                else:
                    # Try to save file to disk (succeeds locally, fails safely in read-only cloud)
                    try:
                        old_path = detected_files.get(category)
                        if old_path and os.path.exists(old_path):
                            os.remove(old_path)
                        
                        new_path = os.path.join(active_dir, uploaded_file.name)
                        with open(new_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        dl.save_metadata(f"uploaded_{category}", uploaded_file.name)
                    except Exception:
                        pass
                    
                    st.toast(f"✅ Loaded {category.replace('_',' ')}: {uploaded_file.name}", icon="✅")
                    replaced_any = True
            
            # Record that we processed these files
            st.session_state.last_processed_upload_ids = uploaded_ids
            if replaced_any:
                detected_files = dl.detect_and_classify_files(active_dir)
                st.session_state.run_report = False
                st.rerun()
        
        st.markdown("##### Loaded Files Status")
        
        # Check if database has BOM
        db_bom_df = None
        try:
            db_bom_df = dl.load_bom_from_db()
        except Exception:
            pass
        
        # Populate loaded_data
        for category in all_categories:
            detected_path = detected_files.get(category)
            is_default_exists = detected_path is not None and os.path.exists(detected_path)
            
            # Check session state buffer first
            in_mem_buffer = st.session_state.get(f"buffer_{category}")
            
            if category == 'BOM':
                if in_mem_buffer is not None:
                    loaded_data[category] = in_mem_buffer
                elif db_bom_df is not None:
                    loaded_data[category] = 'DATABASE'
                elif is_default_exists:
                    loaded_data[category] = detected_path
                continue
                
            display_name = category.replace('_',' ').replace('VGL', 'VIN Generation')
            uploaded_filename = None
            try:
                uploaded_filename = dl.load_metadata(f"uploaded_{category}")
            except Exception:
                pass
                
            if in_mem_buffer is not None:
                loaded_data[category] = in_mem_buffer
                status_icon = "🟢 Uploaded"
                source_label = f"({in_mem_buffer.name})"
            elif is_default_exists:
                loaded_data[category] = detected_path
                if st.session_state.data_source_dir == 'TEST Directory (Sample Data)':
                    status_icon = "🟢 TEST Data loaded"
                    source_label = f"({os.path.basename(detected_path)})"
                elif uploaded_filename and os.path.basename(detected_path) == uploaded_filename:
                    status_icon = "🟢 Uploaded"
                    source_label = f"({uploaded_filename})"
                else:
                    status_icon = "⚪ Pending for upload"
                    source_label = "(No data uploaded)"
            else:
                status_icon = "🔴 Missing"
                source_label = "(Pending for upload)"
                
            st.markdown(f"**{display_name}**: {status_icon} <small style='color:#8896AB'>{source_label}</small>", unsafe_allow_html=True)
            
    with col_engine:
        st.markdown("#### ⚙️ Engine Starting Stocks")
        st.markdown("<small style='color:#8896AB'>Edit clearance counts directly in the table below (Default: 0)</small>", unsafe_allow_html=True)
        
        edited_engine_df = st.data_editor(
            st.session_state.engine_df,
            column_config={
                "Clearance After 6:30AM": st.column_config.NumberColumn(
                    "Clearance Qty",
                    help="Engine stock count at 6:30AM shift start",
                    min_value=0,
                    step=1
                ),
                "Engine Part No": st.column_config.TextColumn(disabled=True),
                "Model": st.column_config.TextColumn(disabled=True),
                "TA Code": st.column_config.TextColumn(disabled=True),
                "TCF Line": st.column_config.TextColumn(disabled=True),
            },
            disabled=["Engine Part No", "Model", "TA Code", "TCF Line"],
            use_container_width=True,
            hide_index=True
        )
        if not edited_engine_df.equals(st.session_state.engine_df):
            st.session_state.engine_df = edited_engine_df
            st.session_state.run_report = False
            try:
                dl.save_engine_stocks_to_db(edited_engine_df)
            except Exception:
                pass
            
        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
        if st.button("Reset Clearances to 0 (Shift Start)", type="secondary", use_container_width=True):
            st.session_state.engine_df = pd.DataFrame(engine_default_data)
            try:
                dl.save_engine_stocks_to_db(st.session_state.engine_df)
            except Exception:
                pass
            now_time = datetime.datetime.now()
            st.session_state.last_reset_time = now_time
            try:
                dl.save_metadata('last_reset_time', now_time.isoformat())
            except Exception:
                pass
            # Clear uploaded file registry in metadata and session state buffers (except BOM which is constant)
            for cat in all_categories:
                if cat == 'BOM':
                    continue  # Master BOM details remain constant all the time
                try:
                    dl.save_metadata(f"uploaded_{cat}", "")
                except Exception:
                    pass
                if f"buffer_{cat}" in st.session_state:
                    del st.session_state[f"buffer_{cat}"]
            st.session_state.run_report = False
            st.toast("🔄 Engine clearances and daily report upload registries reset (Master BOM preserved)!", icon="🔄")
            st.rerun()

core_available = 'BOM' in loaded_data and 'FLOAT_REPORT' in loaded_data

if not core_available:
    st.warning("⚠️ Please ensure the **Master BOM** and **PPC Float Report** are available in the database/workspace or uploaded above to run the dashboard.")
    st.stop()

# ----------------- GENERATE REPORT CONTROL -----------------
if 'run_report' not in st.session_state:
    st.session_state.run_report = False

st.markdown("---")
col_gen1, col_gen2 = st.columns([1.5, 3.5])
with col_gen1:
    btn_label = "🚀 Generate Report" if not st.session_state.run_report else "🔄 Re-generate Report"
    if st.button(btn_label, type="primary", use_container_width=True, key="btn_generate_report_control"):
        st.session_state.run_report = True
        st.rerun()

with col_gen2:
    if not st.session_state.run_report:
        st.info("💡 Files or engine data have been updated. Click **'🚀 Generate Report'** on the left to run calculations.")
    else:
        st.caption("✅ Report is generated. Uploading new files or updating engine clearances will pause auto-runs until you click **'Re-generate Report'**.")

if not st.session_state.run_report:
    st.stop()

# ----------------- PARSING & CALCULATING DATA -----------------
try:
    with st.spinner("⏳ Parsing plant reports and running allocation calculations..."):
        # 1. Load BOM
        if loaded_data['BOM'] == 'DATABASE':
            bom_df = dl.load_bom_from_db()
        else:
            bom_df = dl.load_bom(loaded_data['BOM'])
            try:
                dl.save_bom_to_db(bom_df)
            except Exception:
                pass
        
        # 2. Load Float Report
        float_df = dl.load_float_report(loaded_data['FLOAT_REPORT'])
        
        # 3. Load VGL drops
        tcf1_drops = dl.load_vgl(loaded_data['TCF1_VGL']) if 'TCF1_VGL' in loaded_data else None
        tcf2_drops = dl.load_vgl(loaded_data['TCF2_VGL']) if 'TCF2_VGL' in loaded_data else None
        
        # 4. Parse stocks
        # Wiring Stock
        tcf1_wiring_start = None
        tcf1_wiring_vc_map = {}
        if 'TCF1_WIRING_STOCK' in loaded_data:
            tcf1_wiring_start, tcf1_wiring_vc_map = dl.load_stock_grouped(
                loaded_data['TCF1_WIRING_STOCK'],
                sheet_name='Coverage file 6.30 AM New',
                vc_col_idx=2, part_col_idx=3, qty_col_idx=9
            )
            
        tcf2_wiring_start = None
        tcf2_wiring_vc_map = {}
        if 'TCF2_WIRING_STOCK' in loaded_data:
            tcf2_wiring_start, tcf2_wiring_vc_map = dl.load_stock_grouped(
                loaded_data['TCF2_WIRING_STOCK'],
                sheet_name='coverage file 6.30 pm',
                vc_col_idx=1, part_col_idx=2, qty_col_idx=9
            )
            
        # Cockpit Stock
        # Combine Altroz and Nova cockpits for TCF1
        tcf1_cockpit_start = None
        tcf1_cockpit_vc_map = {}
        
        if 'TCF1_ALTROZ_COCKPIT_STOCK' in loaded_data:
            if tcf1_cockpit_start is None:
                tcf1_cockpit_start = {}
            altroz_start, altroz_map = dl.load_stock_grouped(
                loaded_data['TCF1_ALTROZ_COCKPIT_STOCK'],
                sheet_name='Fresh VIN PPC',
                vc_col_idx=4, part_col_idx=3, qty_col_idx=12, skip_rows=3
            )
            tcf1_cockpit_start.update(altroz_start)
            tcf1_cockpit_vc_map.update(altroz_map)
            
        if 'TCF1_NOVA_COCKPIT_STOCK' in loaded_data:
            if tcf1_cockpit_start is None:
                tcf1_cockpit_start = {}
            nova_start, nova_map = dl.load_stock_grouped(
                loaded_data['TCF1_NOVA_COCKPIT_STOCK'],
                sheet_name='Fresh VIN PPC',
                vc_col_idx=1, part_col_idx=0, qty_col_idx=9, skip_rows=3
            )
            tcf1_cockpit_start.update(nova_start)
            tcf1_cockpit_vc_map.update(nova_map)
            
        tcf2_cockpit_start = None
        tcf2_cockpit_vc_map = {}
        if 'TCF2_COCKPIT_STOCK' in loaded_data:
            tcf2_cockpit_start, tcf2_cockpit_vc_map = dl.load_stock_grouped(
                loaded_data['TCF2_COCKPIT_STOCK'],
                sheet_name='Fresh vin PPC',
                vc_col_idx=3, part_col_idx=1, qty_col_idx=9, skip_rows=3
            )
            
        # Load Engine Stock from data_editor
        engine_stocks_tcf1 = {}
        engine_stocks_tcf2 = {}
        for idx, row in st.session_state.engine_df.iterrows():
            part = str(row['Engine Part No']).strip()
            qty = int(row['Clearance After 6:30AM'])
            if row['TCF Line'] == 'TCF1':
                engine_stocks_tcf1[part] = qty
            else:
                engine_stocks_tcf2[part] = qty

        # ----------------- BACKFLUSH LOGIC (calculate true stock) -----------------
        # TCF1 Backflush
        true_engine_tcf1, eng_cons_tcf1, eng_warn_tcf1 = ae.calculate_true_stock(engine_stocks_tcf1, tcf1_drops, bom_df, 'Engine')
        true_cockpit_tcf1, ck_cons_tcf1, ck_warn_tcf1 = ae.calculate_true_stock(tcf1_cockpit_start, tcf1_drops, bom_df, 'Cockpit')
        true_wiring_tcf1, wh_cons_tcf1, wh_warn_tcf1 = ae.calculate_true_stock(tcf1_wiring_start, tcf1_drops, bom_df, 'Front Wiring')
        
        # TCF2 Backflush
        true_engine_tcf2, eng_cons_tcf2, eng_warn_tcf2 = ae.calculate_true_stock(engine_stocks_tcf2, tcf2_drops, bom_df, 'Engine')
        true_cockpit_tcf2, ck_cons_tcf2, ck_warn_tcf2 = ae.calculate_true_stock(tcf2_cockpit_start, tcf2_drops, bom_df, 'Cockpit')
        true_wiring_tcf2, wh_cons_tcf2, wh_warn_tcf2 = ae.calculate_true_stock(tcf2_wiring_start, tcf2_drops, bom_df, 'Front Wiring')
        
        # ----------------- PBS QUEUE SEPARATION & ALLOCATION -----------------
        # Cabs in PBS must have PBS LIFT not null
        pbs_all = float_df[float_df['PBS LIFT'].notna()].copy()
        
        # Split into holds vs active allocation queue
        pbs_on_hold = pbs_all[pbs_all['HOLD BY'].notna()].copy()
        pbs_active = pbs_all[pbs_all['HOLD BY'].isna()].copy()
        
        # Split active queue by SHOP
        tcf1_queue = pbs_active[pbs_active['SHOP'] == 'TCF1'].copy()
        tcf2_queue = pbs_active[pbs_active['SHOP'] == 'TCF2'].copy()
        
        # Sort chronologically (FIFO)
        tcf1_queue.sort_values(by='PBS LIFT', ascending=True, inplace=True)
        tcf2_queue.sort_values(by='PBS LIFT', ascending=True, inplace=True)
        
        # Run allocation engine
        tcf1_alloc, tcf1_final_stocks = ae.run_allocation(tcf1_queue, bom_df, true_engine_tcf1, true_cockpit_tcf1, true_wiring_tcf1)
        tcf2_alloc, tcf2_final_stocks = ae.run_allocation(tcf2_queue, bom_df, true_engine_tcf2, true_cockpit_tcf2, true_wiring_tcf2)
        
        # Convert allocation lists back to DataFrames
        tcf1_alloc_df = pd.DataFrame(tcf1_alloc)
        tcf2_alloc_df = pd.DataFrame(tcf2_alloc)
        
        # Add Model column by mapping Engine Part No to Model & Line
        if 'engine_df' in st.session_state and not st.session_state.engine_df.empty:
            engine_to_model = dict(zip(st.session_state.engine_df['Engine Part No'].astype(str).str.strip(), st.session_state.engine_df['Model']))
            engine_to_line = dict(zip(st.session_state.engine_df['Engine Part No'].astype(str).str.strip(), st.session_state.engine_df['TCF Line']))
        else:
            engine_to_model = {item['Engine Part No']: item['Model'] for item in engine_default_data}
            engine_to_line = {item['Engine Part No']: item['TCF Line'] for item in engine_default_data}
            
        # Helper function to map model name dynamically with Tayrona override
        def map_row_model(df):
            if df.empty:
                return pd.Series(dtype='object')
            
            # Default mapping from Engine Part
            models = df['Engine_Part'].astype(str).str.strip().map(engine_to_model)
            
            # Override for Tayrona (Safari EV)
            if 'PRODUCT' in df.columns:
                is_tayrona = df['PRODUCT'].astype(str).str.strip().str.upper().str.contains('TAYRONA') | \
                             df['VEHICLE CODE'].astype(str).str.strip().str.startswith('54831927A')
            else:
                is_tayrona = df['VEHICLE CODE'].astype(str).str.strip().str.startswith('54831927A')
                
            models = np.where(is_tayrona, 'SAFARI EV', models)
            return pd.Series(models, index=df.index).fillna('—')
            
        if not tcf1_alloc_df.empty:
            tcf1_alloc_df['Model'] = map_row_model(tcf1_alloc_df)
        else:
            tcf1_alloc_df['Model'] = pd.Series(dtype='object')
            
        if not tcf2_alloc_df.empty:
            tcf2_alloc_df['Model'] = map_row_model(tcf2_alloc_df)
        else:
            tcf2_alloc_df['Model'] = pd.Series(dtype='object')
            
        # Map Engine Part to Model in the raw drop data (VIN Generation)
        if tcf1_drops is not None and not tcf1_drops.empty:
            tcf1_drops['Model'] = map_row_model(tcf1_drops)
            
        if tcf2_drops is not None and not tcf2_drops.empty:
            tcf2_drops['Model'] = map_row_model(tcf2_drops)
        
        # ----------------- STAGEWISE MATERIAL SUMMARY -----------------
        # Get stages for all float report cabs
        float_stages_df = ae.get_paint_float_stages(float_df)
        
        # Combined stock registry for shortage calculation
        combined_true_stocks = {
            'engine': {**true_engine_tcf1, **true_engine_tcf2},
            'cockpit': {**true_cockpit_tcf1, **true_cockpit_tcf2},
            'wiring': {**true_wiring_tcf1, **true_wiring_tcf2}
        }
        
        shortage_report_df = ae.calculate_stagewise_shortage(float_stages_df, bom_df, combined_true_stocks)

        # Build temp_float_df with stage, model, and engine mapping for all downstream views
        def get_summary_product_to_model(prod_name):
            prod = str(prod_name).strip().upper()
            if 'HORNBILL' in prod:
                return 'PUNCH'
            elif 'NOVA' in prod:
                return 'PUNCH.EV'
            elif 'ETURNA' in prod:
                return 'HARRIER.EV'
            elif 'GRAVITAS' in prod:
                return 'SAFARI'
            elif 'Q5' in prod:
                return 'HARRIER'
            elif 'TAYRONA' in prod:
                return 'SAFARI.EV'
            return 'UNKNOWN'
            
        def get_row_paint_stage(row):
            return ae.get_detailed_paint_summary_stage(row)

        if float_df is not None and not float_df.empty:
            temp_float_df = float_df.copy()
            temp_float_df['Model_Mapped'] = temp_float_df['PRODUCT'].apply(get_summary_product_to_model)
            temp_float_df['Stage'] = temp_float_df.apply(get_row_paint_stage, axis=1)
            if bom_df is not None and not bom_df.empty and 'VEHICLE CODE' in temp_float_df.columns:
                vc_to_engine = dict(zip(bom_df['Short Vehicle Code'].astype(str).str.strip(), bom_df['Engine'].astype(str).str.strip()))
                temp_float_df['Engine_Part'] = temp_float_df['VEHICLE CODE'].astype(str).str.strip().str[:9].map(vc_to_engine)
        else:
            temp_float_df = pd.DataFrame()

        ready_count = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '✅ Ready for TCF']) if not tcf1_alloc_df.empty else 0
        blocked_count = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '🚫 Blocked']) if not tcf1_alloc_df.empty else 0
        ready_count_tcf2 = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '✅ Ready for TCF']) if not tcf2_alloc_df.empty else 0
        blocked_count_tcf2 = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '🚫 Blocked']) if not tcf2_alloc_df.empty else 0

except Exception as e:
    st.error(f"❌ Error while running calculations: {e}")
    st.info("Please verify that the uploaded files match the required structure and columns.")
    st.stop()

# ----------------- MAIN PANEL LAYOUT -----------------
# Helper function to render Total Float Details & Cab Search view
def render_total_float_details_view(float_df, default_line="All"):
    st.markdown("### 🔍 Total Float Details & Cab Search")
    st.markdown("""
        Search and filter cabs across the entire Paint Shop float using **BIW Number**, **Vehicle Code (VC)**, and **Paint Stage dropdown options**.
    """)
    
    if float_df is None or float_df.empty:
        st.info("Please load Paint Float report data in the Control Panel to view float details.")
        return
        
    df_search = float_df.copy()
    if 'Stage' not in df_search.columns:
        df_search['Stage'] = df_search.apply(ae.get_detailed_paint_summary_stage, axis=1)
        
    # Search & Filter Controls
    c1, c2, c3, c4, c5 = st.columns([2, 2, 2.5, 2, 2])
    
    with c1:
        biw_query = st.text_input("🔍 BIW Number:", placeholder="e.g. 5012617", key=f"biw_search_{default_line}")
    with c2:
        vc_query = st.text_input("🚙 Vehicle Code (VC):", placeholder="e.g. 54972824A", key=f"vc_search_{default_line}")
    with c3:
        stages_available = ['All Stages'] + sorted(list(df_search['Stage'].dropna().unique()))
        selected_stage = st.selectbox("🎨 Paint Stage Filter:", options=stages_available, key=f"stage_filter_{default_line}")
    with c4:
        shop_options = ['All Shops', 'TCF1', 'TCF2']
        default_idx = shop_options.index(default_line) if default_line in shop_options else 0
        selected_shop = st.selectbox("🏭 Shop / Line Filter:", options=shop_options, index=default_idx, key=f"shop_filter_{default_line}")
    with c5:
        hold_filter = st.selectbox("🛑 Quality Hold Filter:", options=['All Cabs', 'Quality Hold Only', 'Clear Cabs Only'], key=f"hold_filter_{default_line}")
        
    # Apply filtering logic
    if biw_query.strip():
        df_search = df_search[df_search['BIW NUMBER'].astype(str).str.contains(biw_query.strip(), case=False, na=False)]
    if vc_query.strip():
        df_search = df_search[df_search['VEHICLE CODE'].astype(str).str.contains(vc_query.strip(), case=False, na=False)]
    if selected_stage != 'All Stages':
        df_search = df_search[df_search['Stage'] == selected_stage]
    if selected_shop != 'All Shops':
        df_search = df_search[df_search['SHOP'].astype(str).str.upper() == selected_shop.upper()]
    if hold_filter == 'Quality Hold Only':
        df_search = df_search[df_search['HOLD BY'].notna() & (df_search['HOLD BY'].astype(str).str.strip() != '') & (df_search['HOLD BY'].astype(str).str.upper() != 'NONE')]
    elif hold_filter == 'Clear Cabs Only':
        df_search = df_search[df_search['HOLD BY'].isna() | (df_search['HOLD BY'].astype(str).str.strip() == '') | (df_search['HOLD BY'].astype(str).str.upper() == 'NONE')]

    # KPI Summary Cards
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Matching Cabs", f"{len(df_search)} cabs")
    pbs_count = len(df_search[df_search['Stage'] == 'PBS FLOAT'])
    m2.metric("PBS Buffer Cabs", f"{pbs_count} cabs")
    hold_count = len(df_search[df_search['HOLD BY'].notna() & (df_search['HOLD BY'].astype(str).str.strip() != '') & (df_search['HOLD BY'].astype(str).str.upper() != 'NONE')])
    m3.metric("Quality Hold Cabs", f"{hold_count} cabs", delta_color="inverse")
    m4.metric("Total Plant Float", f"{len(float_df)} cabs")

    # Detailed Cab Inspector Card if BIW number searched
    if biw_query.strip() and len(df_search) == 1:
        cab = df_search.iloc[0]
        st.markdown(f"#### 🎴 Inspector Timeline for BIW #{cab.get('BIW NUMBER')}")
        is_dark = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'
        card_bg = "#1E293B" if is_dark else "#F8FAFC"
        border_c = "#334155" if is_dark else "#E2E8F0"
        
        st.markdown(f"""
        <div style="background-color: {card_bg}; border: 1px solid {border_c}; border-radius: 12px; padding: 1.25rem; margin-bottom: 1.5rem;">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem;">
                <div><strong>BIW Number:</strong> <br><span style="font-size: 1.1em; font-weight: bold; color: #3B82F6;">{cab.get('BIW NUMBER', '—')}</span></div>
                <div><strong>VIN:</strong> <br><span style="font-weight: bold;">{cab.get('VIN', '—')}</span></div>
                <div><strong>Vehicle Code:</strong> <br><code>{cab.get('VEHICLE CODE', '—')}</code></div>
                <div><strong>Product / Model:</strong> <br>{cab.get('PRODUCT', '—')} - {cab.get('MODEL', '—')}</div>
                <div><strong>Colour:</strong> <br>{cab.get('COLOUR', '—')}</div>
                <div><strong>Shop / Line:</strong> <br><strong>{cab.get('SHOP', '—')}</strong></div>
                <div><strong>Current Stage:</strong> <br><span style="background-color: #3B82F6; color: white; padding: 3px 8px; border-radius: 6px; font-weight: bold;">{cab.get('Stage', '—')}</span></div>
            </div>
            <hr style="margin: 1rem 0; border: none; border-top: 1px solid {border_c};">
            <div style="font-size: 13px;">
                <strong>🛑 Quality Hold Status:</strong> {f"<span style='color: #EF4444; font-weight: bold;'>HOLD BY: {cab.get('HOLD BY')} | Reason: {cab.get('REASONS S')}</span>" if pd.notna(cab.get('HOLD BY')) and str(cab.get('HOLD BY')).strip() not in ['', 'None'] else "<span style='color: #10B981; font-weight: bold;'>✅ CLEAR (No Quality Hold)</span>"}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Interactive Data Table
    st.markdown("#### 📋 Float Cab Details")
    display_cols = ['BIW NUMBER', 'VIN', 'VEHICLE CODE', 'PRODUCT', 'MODEL', 'COLOUR', 'SHOP', 'Stage', 'HOLD BY', 'REASONS S', 'BIW LIFTING', 'PTCED', 'SEALANT', 'TOPCOAT', 'PBS LIFT']
    available_cols = [c for c in display_cols if c in df_search.columns]
    
    st.dataframe(df_search[available_cols], use_container_width=True, hide_index=True)
    
    # Export options
    import io
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_search[available_cols].to_excel(writer, index=False, sheet_name='Float Details')
    
    st.download_button(
        label="📥 Export Filtered Float Details to Excel",
        data=excel_buffer.getvalue(),
        file_name=f"total_float_details_{default_line}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"export_float_details_{default_line}"
    )

# Toggle between TCF1, TCF2, Total Float Details, Combined Summary & Reports (Opening tab: Summary Report & Excel Download)
tcf_tabs = st.tabs([
    "📈 Summary Report & Excel Download",
    "🏭 TCF 1 Line (Altroz/Punch/Nova)", 
    "🏭 TCF 2 Line (Harrier/Safari)", 
    "🔍 Total Float Details & Search",
    "📊 Combined Summary & Material Shortages"
])

# Helper function to style allocation dataframe rows
def style_alloc_table(df):
    if df.empty:
        return df
    
    is_dark = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'
    
    def get_row_style(row):
        status = row.get('STATUS')
        if status == '✅ Ready for TCF':
            if is_dark:
                return ['background-color: #064E3B; color: #D1FAE5'] * len(row)
            else:
                return ['background-color: #F0FAF4; color: #166534'] * len(row)
        elif status == '🚫 Blocked':
            if is_dark:
                return ['background-color: #7F1D1D; color: #FEE2E2'] * len(row)
            else:
                return ['background-color: #FFF5F5; color: #B91C1C'] * len(row)
        else:
            if is_dark:
                return ['background-color: #78350F; color: #FEF3C7'] * len(row)
            else:
                return ['background-color: #FFFBEB; color: #92400E'] * len(row)
            
    return df.style.apply(get_row_style, axis=1)

# Helper function to render horizontal bar charts of stocks
def plot_stock_chart(start, true, final, title):
    if not start:
        st.info(f"No stock data loaded for: {title}")
        return
    parts = list(start.keys())
    
    # Limit to top 15 parts to prevent visual clutter
    if len(parts) > 15:
        parts = parts[:15]
        
    start_vals = [start.get(p, 0) for p in parts]
    true_vals = [true.get(p, 0) for p in parts]
    final_vals = [final.get(p, 0) for p in parts]
    
    y = np.arange(len(parts))
    width = 0.25
    
    is_dark = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'
    
    # Theme configuration
    bg_color = '#0F172A' if is_dark else '#F8FAFC'
    face_color = '#1E293B' if is_dark else '#FFFFFF'
    label_color = '#94A3B8' if is_dark else '#374A6B'
    title_color = '#F8FAFC' if is_dark else '#1B2A4A'
    border_color = '#334155' if is_dark else '#E8ECF1'
    grid_color = '#334155' if is_dark else '#F1F5F9'
    
    fig, ax = plt.subplots(figsize=(10, min(6, len(parts)*0.4 + 1.5)))
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(face_color)
    
    # Colors: Slate, Royal Blue / Light Indigo, Emerald Green
    start_color = '#64748B' if is_dark else '#94A3B8'
    true_color = '#6366F1' if is_dark else '#0D9488'
    final_color = '#10B981' if is_dark else '#22C55E'
    
    ax.barh(y - width, start_vals, width, label='Shift Start Stock', color=start_color, edgecolor=face_color, linewidth=0.5)
    ax.barh(y, true_vals, width, label='True Current Stock', color=true_color, edgecolor=face_color, linewidth=0.5)
    ax.barh(y + width, final_vals, width, label='Post-Alloc Virtual Stock', color=final_color, edgecolor=face_color, linewidth=0.5)
    
    ax.set_ylabel('Part Numbers', fontsize=10, fontweight='semibold', color=label_color)
    ax.set_xlabel('Quantity', fontsize=10, fontweight='semibold', color=label_color)
    ax.set_title(title, fontsize=12, fontweight='bold', pad=15, color=title_color)
    ax.set_yticks(y)
    ax.set_yticklabels(parts, fontsize=8, color=label_color)
    ax.tick_params(axis='x', colors=label_color)
    ax.legend(frameon=True, facecolor=face_color, edgecolor=border_color, labelcolor=label_color, fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(border_color)
    ax.spines['bottom'].set_color(border_color)
    ax.grid(axis='x', color=grid_color, linewidth=0.5)
    plt.tight_layout()
    st.pyplot(fig)

# ----------------- TAB 2: TCF 1 LINE -----------------
with tcf_tabs[1]:
    # KPIs
    ready_count = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '✅ Ready for TCF']) if not tcf1_alloc_df.empty else 0
    blocked_count = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '🚫 Blocked']) if not tcf1_alloc_df.empty else 0
    issue_count = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'].str.startswith('⚠️', na=False)]) if not tcf1_alloc_df.empty else 0
    total_drops = len(tcf1_drops) if tcf1_drops is not None else 0
    
    tcf1_ok = len(tcf1_queue)
    tcf1_hold = len(pbs_on_hold[pbs_on_hold['SHOP'] == 'TCF1']) if pbs_on_hold is not None else 0
    tcf1_total = tcf1_ok + tcf1_hold
    
    kpi_cols = st.columns(4)
    kpi_cols[0].metric("VIN Generation", f"{total_drops} cabs", help="Cabs built in TCF1 since shift start")
    kpi_cols[1].metric("PBS Current Stock", f"{tcf1_total} cabs (OK: {tcf1_ok} | Hold: {tcf1_hold})", help="Total cabs in TCF1 PBS buffer (Active unblocked + Quality holds)")
    kpi_cols[2].metric("✅ Ready for TCF", f"{ready_count} cabs", delta=f"+{ready_count} alloc")
    kpi_cols[3].metric("🚫 Blocked (Stock Out)", f"{blocked_count} cabs", delta=f"-{blocked_count} wait", delta_color="inverse")
    
    line_subtabs = st.tabs(["📋 FIFO Allocation Queue", "🔍 Total Float Details & Search"])
    
    # Subtab 1: Queue
    with line_subtabs[0]:
        st.markdown("### TCF1 FIFO Buffer Queue Status")
        if tcf1_alloc_df.empty:
            st.info("No active cabs in TCF1 PBS queue.")
        else:
            # Filter to show only Ready for TCF and Blocked statuses
            filtered_df = tcf1_alloc_df[tcf1_alloc_df['STATUS'].isin(['✅ Ready for TCF', '🚫 Blocked'])].copy()
            
            # Apply any manual planner overrides from session_state
            if 'tcf1_manual_overrides' not in st.session_state:
                st.session_state.tcf1_manual_overrides = {}
            for biw_key, override in st.session_state.tcf1_manual_overrides.items():
                mask = filtered_df['BIW NUMBER'].astype(str) == str(biw_key)
                if mask.any():
                    filtered_df.loc[mask, 'STATUS'] = override['status']
                    filtered_df.loc[mask, 'BLOCKING_REASON'] = override['reason']
            
            search_biw = st.text_input("🔍 Quick Search by BIW Number:", key="tcf1_biw_search")
            if search_biw:
                filtered_df = filtered_df[filtered_df['BIW NUMBER'].astype(str).str.contains(search_biw.strip())]
                
            display_cols = ['BIW NUMBER', 'Model', 'VEHICLE CODE', 'STATUS', 'BLOCKING_REASON', 'PBS LIFT', 'Engine_Part', 'Cockpit_Part', 'Wiring_Part', 'Engine_Stock_After', 'Cockpit_Stock_After', 'Wiring_Stock_After']
            
            st.caption("✏️ **Planner Edit Mode** — Click any cell in the **Status** or **Blocking Reason** column to change it. Changes are saved automatically.")
            
            status_options = ['✅ Ready for TCF', '🚫 Blocked', '⚠️ PBS Hold']
            
            edited_tcf1 = st.data_editor(
                filtered_df[display_cols],
                use_container_width=True,
                hide_index=True,
                key="tcf1_queue_editor",
                column_config={
                    "BIW NUMBER": st.column_config.TextColumn("BIW NUMBER", disabled=True),
                    "Model": st.column_config.TextColumn("Model", disabled=True),
                    "VEHICLE CODE": st.column_config.TextColumn("VEHICLE CODE", disabled=True),
                    "STATUS": st.column_config.SelectboxColumn(
                        "STATUS",
                        options=status_options,
                        required=True,
                        help="Select cab status: Ready, Blocked, or PBS Hold"
                    ),
                    "BLOCKING_REASON": st.column_config.TextColumn(
                        "BLOCKING REASON",
                        help="Enter blocking/hold reason (e.g., quality issue, part shortage, PBS hold)"
                    ),
                    "PBS LIFT": st.column_config.TextColumn("PBS LIFT", disabled=True),
                    "Engine_Part": st.column_config.TextColumn("Engine Part", disabled=True),
                    "Cockpit_Part": st.column_config.TextColumn("Cockpit Part", disabled=True),
                    "Wiring_Part": st.column_config.TextColumn("Wiring Part", disabled=True),
                    "Engine_Stock_After": st.column_config.NumberColumn("Eng Stock After", disabled=True),
                    "Cockpit_Stock_After": st.column_config.NumberColumn("CK Stock After", disabled=True),
                    "Wiring_Stock_After": st.column_config.NumberColumn("WH Stock After", disabled=True),
                },
            )
            
            # Detect and persist planner edits
            original_display = filtered_df[display_cols].reset_index(drop=True)
            edited_display = edited_tcf1.reset_index(drop=True)
            if not original_display.equals(edited_display):
                for i in range(len(edited_display)):
                    orig_status = str(original_display.at[i, 'STATUS']) if i < len(original_display) else ''
                    new_status = str(edited_display.at[i, 'STATUS'])
                    orig_reason = str(original_display.at[i, 'BLOCKING_REASON']) if i < len(original_display) else ''
                    new_reason = str(edited_display.at[i, 'BLOCKING_REASON'])
                    if orig_status != new_status or orig_reason != new_reason:
                        biw_key = str(edited_display.at[i, 'BIW NUMBER'])
                        st.session_state.tcf1_manual_overrides[biw_key] = {
                            'status': new_status,
                            'reason': new_reason
                        }
                st.toast("✅ Planner override saved!", icon="✏️")
                # Update filtered_df to reflect edits for Excel downloads
                filtered_df.update(edited_tcf1)
            
            # Excel download buttons for Ready to TCF and Blocked with Reason
            import io
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            import openpyxl.utils
            
            dl_cols = st.columns(2)
            
            # Ready to TCF Excel
            ready_df_tcf1 = filtered_df[filtered_df['STATUS'] == '✅ Ready for TCF'][display_cols].copy()
            if not ready_df_tcf1.empty:
                buf_ready = io.BytesIO()
                with pd.ExcelWriter(buf_ready, engine='openpyxl') as writer:
                    ready_df_tcf1.to_excel(writer, index=False, sheet_name='Ready to TCF1')
                    ws = writer.sheets['Ready to TCF1']
                    hdr_fill = PatternFill(start_color='D8F3E5', end_color='D8F3E5', fill_type='solid')
                    hdr_font = Font(name='Calibri', size=11, bold=True, color='1B4D32')
                    thin_b = Border(left=Side(style='thin', color='BFBFBF'), right=Side(style='thin', color='BFBFBF'), top=Side(style='thin', color='BFBFBF'), bottom=Side(style='thin', color='BFBFBF'))
                    for c in range(1, len(ready_df_tcf1.columns) + 1):
                        cell = ws.cell(row=1, column=c)
                        cell.font = hdr_font
                        cell.fill = hdr_fill
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                        cell.border = thin_b
                    for r in range(2, len(ready_df_tcf1) + 2):
                        for c in range(1, len(ready_df_tcf1.columns) + 1):
                            cell = ws.cell(row=r, column=c)
                            cell.border = thin_b
                            cell.alignment = Alignment(horizontal='center', vertical='center')
                            cell.font = Font(name='Calibri', size=10)
                    for col in ws.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        ws.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = max(max_len + 3, 12)
                with dl_cols[0]:
                    st.download_button(
                        label=f"📥 Ready to TCF1 ({len(ready_df_tcf1)} cabs)",
                        data=buf_ready.getvalue(),
                        file_name="TCF1_Ready_to_Build.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_ready_tcf1"
                    )
            
            # Blocked with Reason Excel (includes both 🚫 Blocked and ⚠️ PBS Hold)
            blocked_df_tcf1 = filtered_df[filtered_df['STATUS'].isin(['🚫 Blocked', '⚠️ PBS Hold'])][display_cols].copy()
            if not blocked_df_tcf1.empty:
                buf_blocked = io.BytesIO()
                with pd.ExcelWriter(buf_blocked, engine='openpyxl') as writer:
                    blocked_df_tcf1.to_excel(writer, index=False, sheet_name='Blocked TCF1')
                    ws = writer.sheets['Blocked TCF1']
                    hdr_fill = PatternFill(start_color='FFD1D1', end_color='FFD1D1', fill_type='solid')
                    hdr_font = Font(name='Calibri', size=11, bold=True, color='5C1D1B')
                    thin_b = Border(left=Side(style='thin', color='BFBFBF'), right=Side(style='thin', color='BFBFBF'), top=Side(style='thin', color='BFBFBF'), bottom=Side(style='thin', color='BFBFBF'))
                    for c in range(1, len(blocked_df_tcf1.columns) + 1):
                        cell = ws.cell(row=1, column=c)
                        cell.font = hdr_font
                        cell.fill = hdr_fill
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                        cell.border = thin_b
                    for r in range(2, len(blocked_df_tcf1) + 2):
                        for c in range(1, len(blocked_df_tcf1.columns) + 1):
                            cell = ws.cell(row=r, column=c)
                            cell.border = thin_b
                            cell.alignment = Alignment(horizontal='center', vertical='center')
                            cell.font = Font(name='Calibri', size=10)
                            # Highlight blocking reason column in light red
                            if c == 5:  # BLOCKING_REASON column
                                cell.fill = PatternFill(start_color='FFF0F0', end_color='FFF0F0', fill_type='solid')
                    for col in ws.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        ws.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = max(max_len + 3, 12)
                with dl_cols[1]:
                    st.download_button(
                        label=f"📥 Blocked with Reason ({len(blocked_df_tcf1)} cabs)",
                        data=buf_blocked.getvalue(),
                        file_name="TCF1_Blocked_with_Reason.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_blocked_tcf1"
                    )
            
    # Subtab 2: Total Float Details
    with line_subtabs[1]:
        render_total_float_details_view(temp_float_df, default_line="TCF1")

# ----------------- TAB 3: TCF 2 LINE -----------------
with tcf_tabs[2]:
    # KPIs
    ready_count_tcf2 = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '✅ Ready for TCF']) if not tcf2_alloc_df.empty else 0
    blocked_count_tcf2 = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '🚫 Blocked']) if not tcf2_alloc_df.empty else 0
    issue_count_tcf2 = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'].str.startswith('⚠️', na=False)]) if not tcf2_alloc_df.empty else 0
    total_drops_tcf2 = len(tcf2_drops) if tcf2_drops is not None else 0
    
    tcf2_ok = len(tcf2_queue)
    tcf2_hold = len(pbs_on_hold[pbs_on_hold['SHOP'] == 'TCF2']) if pbs_on_hold is not None else 0
    tcf2_total = tcf2_ok + tcf2_hold
    
    kpi_cols_tcf2 = st.columns(4)
    kpi_cols_tcf2[0].metric("VIN Generation", f"{total_drops_tcf2} cabs", help="Cabs built in TCF2 since shift start")
    kpi_cols_tcf2[1].metric("PBS Current Stock", f"{tcf2_total} cabs (OK: {tcf2_ok} | Hold: {tcf2_hold})", help="Total cabs in TCF2 PBS buffer (Active unblocked + Quality holds)")
    kpi_cols_tcf2[2].metric("✅ Ready for TCF", f"{ready_count_tcf2} cabs", delta=f"+{ready_count_tcf2} alloc")
    kpi_cols_tcf2[3].metric("🚫 Blocked (Stock Out)", f"{blocked_count_tcf2} cabs", delta=f"-{blocked_count_tcf2} wait", delta_color="inverse")
    
    line_subtabs_tcf2 = st.tabs(["📋 FIFO Allocation Queue", "🔍 Total Float Details & Search"])
    
    # Subtab 1: Queue
    with line_subtabs_tcf2[0]:
        st.markdown("### TCF2 FIFO Buffer Queue Status")
        if tcf2_alloc_df.empty:
            st.info("No active cabs in TCF2 PBS queue.")
        else:
            # Filter to show only Ready for TCF and Blocked statuses
            filtered_df_tcf2 = tcf2_alloc_df[tcf2_alloc_df['STATUS'].isin(['✅ Ready for TCF', '🚫 Blocked'])].copy()
            
            # Apply any manual planner overrides from session_state
            if 'tcf2_manual_overrides' not in st.session_state:
                st.session_state.tcf2_manual_overrides = {}
            for biw_key, override in st.session_state.tcf2_manual_overrides.items():
                mask = filtered_df_tcf2['BIW NUMBER'].astype(str) == str(biw_key)
                if mask.any():
                    filtered_df_tcf2.loc[mask, 'STATUS'] = override['status']
                    filtered_df_tcf2.loc[mask, 'BLOCKING_REASON'] = override['reason']
            
            search_biw_tcf2 = st.text_input("🔍 Quick Search by BIW Number:", key="tcf2_biw_search")
            if search_biw_tcf2:
                filtered_df_tcf2 = filtered_df_tcf2[filtered_df_tcf2['BIW NUMBER'].astype(str).str.contains(search_biw_tcf2.strip())]
                
            display_cols = ['BIW NUMBER', 'Model', 'VEHICLE CODE', 'STATUS', 'BLOCKING_REASON', 'PBS LIFT', 'Engine_Part', 'Cockpit_Part', 'Wiring_Part', 'Engine_Stock_After', 'Cockpit_Stock_After', 'Wiring_Stock_After']
            
            st.caption("✏️ **Planner Edit Mode** — Click any cell in the **Status** or **Blocking Reason** column to change it. Changes are saved automatically.")
            
            status_options = ['✅ Ready for TCF', '🚫 Blocked', '⚠️ PBS Hold']
            
            edited_tcf2 = st.data_editor(
                filtered_df_tcf2[display_cols],
                use_container_width=True,
                hide_index=True,
                key="tcf2_queue_editor",
                column_config={
                    "BIW NUMBER": st.column_config.TextColumn("BIW NUMBER", disabled=True),
                    "Model": st.column_config.TextColumn("Model", disabled=True),
                    "VEHICLE CODE": st.column_config.TextColumn("VEHICLE CODE", disabled=True),
                    "STATUS": st.column_config.SelectboxColumn(
                        "STATUS",
                        options=status_options,
                        required=True,
                        help="Select cab status: Ready, Blocked, or PBS Hold"
                    ),
                    "BLOCKING_REASON": st.column_config.TextColumn(
                        "BLOCKING REASON",
                        help="Enter blocking/hold reason (e.g., quality issue, part shortage, PBS hold)"
                    ),
                    "PBS LIFT": st.column_config.TextColumn("PBS LIFT", disabled=True),
                    "Engine_Part": st.column_config.TextColumn("Engine Part", disabled=True),
                    "Cockpit_Part": st.column_config.TextColumn("Cockpit Part", disabled=True),
                    "Wiring_Part": st.column_config.TextColumn("Wiring Part", disabled=True),
                    "Engine_Stock_After": st.column_config.NumberColumn("Eng Stock After", disabled=True),
                    "Cockpit_Stock_After": st.column_config.NumberColumn("CK Stock After", disabled=True),
                    "Wiring_Stock_After": st.column_config.NumberColumn("WH Stock After", disabled=True),
                },
            )
            
            # Detect and persist planner edits
            original_display_tcf2 = filtered_df_tcf2[display_cols].reset_index(drop=True)
            edited_display_tcf2 = edited_tcf2.reset_index(drop=True)
            if not original_display_tcf2.equals(edited_display_tcf2):
                for i in range(len(edited_display_tcf2)):
                    orig_status = str(original_display_tcf2.at[i, 'STATUS']) if i < len(original_display_tcf2) else ''
                    new_status = str(edited_display_tcf2.at[i, 'STATUS'])
                    orig_reason = str(original_display_tcf2.at[i, 'BLOCKING_REASON']) if i < len(original_display_tcf2) else ''
                    new_reason = str(edited_display_tcf2.at[i, 'BLOCKING_REASON'])
                    if orig_status != new_status or orig_reason != new_reason:
                        biw_key = str(edited_display_tcf2.at[i, 'BIW NUMBER'])
                        st.session_state.tcf2_manual_overrides[biw_key] = {
                            'status': new_status,
                            'reason': new_reason
                        }
                st.toast("✅ Planner override saved!", icon="✏️")
                # Update filtered_df_tcf2 to reflect edits for Excel downloads
                filtered_df_tcf2.update(edited_tcf2)
            
            # Excel download buttons for Ready to TCF and Blocked with Reason
            import io
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            import openpyxl.utils
            
            dl_cols_tcf2 = st.columns(2)
            
            # Ready to TCF Excel
            ready_df_tcf2 = filtered_df_tcf2[filtered_df_tcf2['STATUS'] == '✅ Ready for TCF'][display_cols].copy()
            if not ready_df_tcf2.empty:
                buf_ready2 = io.BytesIO()
                with pd.ExcelWriter(buf_ready2, engine='openpyxl') as writer:
                    ready_df_tcf2.to_excel(writer, index=False, sheet_name='Ready to TCF2')
                    ws = writer.sheets['Ready to TCF2']
                    hdr_fill = PatternFill(start_color='D8F3E5', end_color='D8F3E5', fill_type='solid')
                    hdr_font = Font(name='Calibri', size=11, bold=True, color='1B4D32')
                    thin_b = Border(left=Side(style='thin', color='BFBFBF'), right=Side(style='thin', color='BFBFBF'), top=Side(style='thin', color='BFBFBF'), bottom=Side(style='thin', color='BFBFBF'))
                    for c in range(1, len(ready_df_tcf2.columns) + 1):
                        cell = ws.cell(row=1, column=c)
                        cell.font = hdr_font
                        cell.fill = hdr_fill
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                        cell.border = thin_b
                    for r in range(2, len(ready_df_tcf2) + 2):
                        for c in range(1, len(ready_df_tcf2.columns) + 1):
                            cell = ws.cell(row=r, column=c)
                            cell.border = thin_b
                            cell.alignment = Alignment(horizontal='center', vertical='center')
                            cell.font = Font(name='Calibri', size=10)
                    for col in ws.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        ws.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = max(max_len + 3, 12)
                with dl_cols_tcf2[0]:
                    st.download_button(
                        label=f"📥 Ready to TCF2 ({len(ready_df_tcf2)} cabs)",
                        data=buf_ready2.getvalue(),
                        file_name="TCF2_Ready_to_Build.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_ready_tcf2"
                    )
            
            # Blocked with Reason Excel (includes both 🚫 Blocked and ⚠️ PBS Hold)
            blocked_df_tcf2 = filtered_df_tcf2[filtered_df_tcf2['STATUS'].isin(['🚫 Blocked', '⚠️ PBS Hold'])][display_cols].copy()
            if not blocked_df_tcf2.empty:
                buf_blocked2 = io.BytesIO()
                with pd.ExcelWriter(buf_blocked2, engine='openpyxl') as writer:
                    blocked_df_tcf2.to_excel(writer, index=False, sheet_name='Blocked TCF2')
                    ws = writer.sheets['Blocked TCF2']
                    hdr_fill = PatternFill(start_color='FFD1D1', end_color='FFD1D1', fill_type='solid')
                    hdr_font = Font(name='Calibri', size=11, bold=True, color='5C1D1B')
                    thin_b = Border(left=Side(style='thin', color='BFBFBF'), right=Side(style='thin', color='BFBFBF'), top=Side(style='thin', color='BFBFBF'), bottom=Side(style='thin', color='BFBFBF'))
                    for c in range(1, len(blocked_df_tcf2.columns) + 1):
                        cell = ws.cell(row=1, column=c)
                        cell.font = hdr_font
                        cell.fill = hdr_fill
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                        cell.border = thin_b
                    for r in range(2, len(blocked_df_tcf2) + 2):
                        for c in range(1, len(blocked_df_tcf2.columns) + 1):
                            cell = ws.cell(row=r, column=c)
                            cell.border = thin_b
                            cell.alignment = Alignment(horizontal='center', vertical='center')
                            cell.font = Font(name='Calibri', size=10)
                            # Highlight blocking reason column in light red
                            if c == 5:  # BLOCKING_REASON column
                                cell.fill = PatternFill(start_color='FFF0F0', end_color='FFF0F0', fill_type='solid')
                    for col in ws.columns:
                        max_len = max(len(str(cell.value or '')) for cell in col)
                        ws.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = max(max_len + 3, 12)
                with dl_cols_tcf2[1]:
                    st.download_button(
                        label=f"📥 Blocked with Reason ({len(blocked_df_tcf2)} cabs)",
                        data=buf_blocked2.getvalue(),
                        file_name="TCF2_Blocked_with_Reason.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_blocked_tcf2"
                    )
            
    # Subtab 2: Total Float Details
    with line_subtabs_tcf2[1]:
        render_total_float_details_view(temp_float_df, default_line="TCF2")

# ----------------- TAB 4: TOTAL FLOAT DETAILS & SEARCH -----------------
with tcf_tabs[3]:
    render_total_float_details_view(temp_float_df, default_line="All")

# ----------------- TAB 5: COMBINED SUMMARY & SHORTAGES -----------------
with tcf_tabs[4]:
    st.markdown("### 📊 Combined Buffer Performance")
    
    # Combined Metrics
    tot_pbs = len(float_df[float_df['PBS LIFT'].notna()])
    tot_hold = len(float_df[float_df['PBS LIFT'].notna() & float_df['HOLD BY'].notna()])
    tot_ready = ready_count + ready_count_tcf2
    tot_blocked = blocked_count + blocked_count_tcf2
    
    metric_cols = st.columns(4)
    metric_cols[0].metric("Total PBS Inventory", f"{tot_pbs} cabs")
    metric_cols[1].metric("Quality Holds (PBS)", f"{tot_hold} cabs", help="Cabs in PBS on Quality hold")
    metric_cols[2].metric("Total Clear to Build (CTB)", f"{tot_ready} cabs", delta=f"{int(tot_ready/max(1, tot_pbs-tot_hold)*100)}% CTB Rate")
    metric_cols[3].metric("Total Blocked", f"{tot_blocked} cabs", delta=f"{int(tot_blocked/max(1, tot_pbs-tot_hold)*100)}% Stock Out Rate", delta_color="inverse")
    
    st.markdown("---")
    
    # Quality Holds Section
    st.markdown("### 🛑 PBS Quality Holds Registry")
    
    # Avoid duplicate BIW numbers and sort by SHOP (TCF1 to TCF2)
    if not pbs_on_hold.empty:
        pbs_on_hold_cleaned = pbs_on_hold.drop_duplicates(subset=['BIW NUMBER']).sort_values(by=['SHOP', 'PBS LIFT'], ascending=[True, True]).copy()
        
        # Add Model column by mapping Short Vehicle Code to BOM's Engine part, then mapping Engine part to Model name
        if bom_df is not None and not bom_df.empty:
            vc_to_engine = dict(zip(bom_df['Short Vehicle Code'].astype(str).str.strip(), bom_df['Engine'].astype(str).str.strip()))
            short_vcs = pbs_on_hold_cleaned['VEHICLE CODE'].astype(str).str.strip().str[:9]
            mapped_engines = short_vcs.map(vc_to_engine)
            pbs_on_hold_cleaned['Model'] = mapped_engines.map(engine_to_model)
        else:
            pbs_on_hold_cleaned['Model'] = pd.Series(dtype='object', index=pbs_on_hold_cleaned.index)
            
        # Override for Tayrona
        if 'PRODUCT' in pbs_on_hold_cleaned.columns:
            is_tayrona = pbs_on_hold_cleaned['PRODUCT'].astype(str).str.strip().str.upper().str.contains('TAYRONA') | \
                         pbs_on_hold_cleaned['VEHICLE CODE'].astype(str).str.strip().str.startswith('54831927A')
        else:
            is_tayrona = pbs_on_hold_cleaned['VEHICLE CODE'].astype(str).str.strip().str.startswith('54831927A')
            
        pbs_on_hold_cleaned['Model'] = np.where(is_tayrona, 'SAFARI EV', pbs_on_hold_cleaned['Model'])
        pbs_on_hold_cleaned['Model'] = pbs_on_hold_cleaned['Model'].fillna('—')
            
        # Standardize Colour column name
        colour_col = None
        for col in pbs_on_hold_cleaned.columns:
            if str(col).strip().upper() in ['COLOUR', 'COLOR']:
                colour_col = col
                break
        if colour_col:
            pbs_on_hold_cleaned['Colour'] = pbs_on_hold_cleaned[colour_col].fillna('—')
        else:
            pbs_on_hold_cleaned['Colour'] = '—'
    else:
        pbs_on_hold_cleaned = pd.DataFrame()
        
    if pbs_on_hold_cleaned.empty:
        st.success("🎉 Excellent! No cabs currently on quality hold in the PBS buffer.")
    else:
        st.warning(f"⚠️ {len(pbs_on_hold_cleaned)} unique cabs are currently held in PBS and skipped from Clear-to-Build checks.")
        
        # Select and order display columns
        display_hold_cols = []
        possible_cols = ['BIW NUMBER', 'Model', 'Colour', 'VIN', 'VEHICLE CODE', 'SHOP', 'HOLD BY', 'REASONS S', 'PBS LIFT']
        for col in possible_cols:
            if col in pbs_on_hold_cleaned.columns:
                display_hold_cols.append(col)
                
        st.dataframe(
            pbs_on_hold_cleaned[display_hold_cols],
            use_container_width=True,
            hide_index=True
        )
        
        # Export to Excel option
        import io
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pbs_on_hold_cleaned[display_hold_cols].to_excel(writer, index=False, sheet_name='Quality Holds')
        excel_data = excel_buffer.getvalue()
        
        st.download_button(
            label="📥 Export Quality Holds to Excel",
            data=excel_data,
            file_name="pbs_quality_holds.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="export_quality_holds"
        )
        
    st.markdown("---")
    
    # Shortage Report - Stagewise Float
    # Shortage Report - Stagewise Float
    st.markdown("### 🔮 Stagewise Shortage Report")
    st.markdown("""
        This report tracks material shortages calculated against three stages of the paint float:
        1. **Shortage (PBS Float)**: Shortage against cabs currently in the PBS buffer stage (`1. PBS LIFT`).
        2. **Shortage (Sealant Float)**: Cumulative shortage against cabs from PBS up to the Sealant stage (`1. PBS LIFT` + `2. TOPCOAT` + `3. SEALANT`).
        3. **Shortage (Total Float)**: Cumulative shortage against all cabs in the paint float (`BIW LIFTING` through `PBS LIFT`).
        
        *Only parts experiencing a shortage in at least one category are displayed.*
    """)
    
    # Calculate shortages: against PBS Float, up to Sealant Float, against Total Float
    shortage_data = []
    if float_stages_df is not None and not float_stages_df.empty:
        demands = {} # {(shop, agg_type, part_no): {stage: count}}
        stages_of_interest = ['1. PBS LIFT', '2. TOPCOAT', '3. SEALANT', '4. PTCED', '5. BIW LIFTING']
        
        bom_map = {}
        if bom_df is not None:
            for idx, row in bom_df.iterrows():
                vc = str(row['Short Vehicle Code']).strip()
                bom_map[vc] = {
                    'Engine': str(row.get('Engine', '')).strip(),
                    'Cockpit': str(row.get('Cockpit', '')).strip(),
                    'Front Wiring': str(row.get('Front Wiring', '')).strip()
                }
                
        for idx, row in float_stages_df.iterrows():
            stage = row['Paint_Stage']
            if stage not in stages_of_interest:
                continue
            shop = str(row.get('SHOP', 'Unknown')).strip()
            full_vc = str(row.get('VEHICLE CODE', '')).strip()
            short_vc = full_vc[:9]
            
            parts = bom_map.get(short_vc)
            if not parts:
                continue
                
            for agg_type in ['Engine', 'Cockpit', 'Front Wiring']:
                part_no = parts.get(agg_type)
                if not part_no or part_no in ['0', 'None', 'nan', '']:
                    continue
                    
                key = (shop, agg_type, part_no)
                if key not in demands:
                    demands[key] = {stg: 0 for stg in stages_of_interest}
                demands[key][stage] += 1
                
        for (shop, agg_type, part_no), stage_counts in demands.items():
            stock = 0
            if agg_type == 'Engine' and true_engine_tcf1 is not None and true_engine_tcf2 is not None:
                stock = true_engine_tcf1.get(part_no, 0) if shop == 'TCF1' else true_engine_tcf2.get(part_no, 0)
            elif agg_type == 'Cockpit' and true_cockpit_tcf1 is not None and true_cockpit_tcf2 is not None:
                stock = true_cockpit_tcf1.get(part_no, 0) if shop == 'TCF1' else true_cockpit_tcf2.get(part_no, 0)
            elif agg_type == 'Front Wiring' and true_wiring_tcf1 is not None and true_wiring_tcf2 is not None:
                stock = true_wiring_tcf1.get(part_no, 0) if shop == 'TCF1' else true_wiring_tcf2.get(part_no, 0)
                
            d_pbs = stage_counts.get('1. PBS LIFT', 0)
            d_sealant = d_pbs + stage_counts.get('2. TOPCOAT', 0) + stage_counts.get('3. SEALANT', 0)
            d_total = d_sealant + stage_counts.get('4. PTCED', 0) + stage_counts.get('5. BIW LIFTING', 0)
            
            sh_pbs = max(0, d_pbs - stock)
            sh_sealant = max(0, d_sealant - stock)
            sh_total = max(0, d_total - stock)
            
            if sh_pbs > 0 or sh_sealant > 0 or sh_total > 0:
                model_name = '—'
                if agg_type == 'Engine' and engine_to_model:
                    model_name = engine_to_model.get(part_no, '—')
                    
                part_cat = agg_type
                if agg_type == 'Engine':
                    if part_no in ['546816111212', '547380400103'] or 'EV' in str(model_name).upper() or 'NOVA' in str(model_name).upper():
                        part_cat = 'Battery'
                        
                shortage_data.append({
                    'TCF Line': shop,
                    'Part Category': part_cat,
                    'Part Number': part_no,
                    'Model': model_name,
                    'Current Stock': stock,
                    'With respect to PBS FLOAT': sh_pbs,
                    'With respect to Sealant FLOAT': sh_sealant,
                    'With respect to Total FLOAT': sh_total
                })
                
    shortage_summary_df = pd.DataFrame(shortage_data)
    
    # Filter
    selected_categories = st.multiselect(
        "Filter by part category:",
        options=['Engine', 'Battery', 'Cockpit', 'Front Wiring'],
        default=['Engine', 'Battery', 'Cockpit', 'Front Wiring'],
        key="shortage_categories_filter"
    )
    
    if not shortage_summary_df.empty:
        # Normalize and filter
        filtered_shortage_df = shortage_summary_df[shortage_summary_df['Part Category'].isin(selected_categories)].copy()
    else:
        filtered_shortage_df = pd.DataFrame()
        
    if filtered_shortage_df.empty:
        st.success("🎉 No material shortages predicted for any parts in the paint float!")
    else:
        # Styling function to highlight shortage values > 0
        def style_shortage_report(df):
            if df.empty:
                return df
            is_dark = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'
            bg_color = '#7F1D1D' if is_dark else '#FFF5F5'
            text_color = '#FEE2E2' if is_dark else '#B91C1C'
            
            def highlight_shortage(val):
                try:
                    val_num = int(val)
                    if val_num > 0:
                        return f'background-color: {bg_color}; color: {text_color}; font-weight: bold;'
                except Exception:
                    pass
                return ''
            return df.style.map(highlight_shortage, subset=['With respect to PBS FLOAT', 'With respect to Sealant FLOAT', 'With respect to Total FLOAT'])
            
        st.dataframe(
            style_shortage_report(filtered_shortage_df),
            use_container_width=True,
            hide_index=True
        )
        
        # Export to Excel option
        import io
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            filtered_shortage_df.to_excel(writer, index=False, sheet_name='Shortages')
        excel_data = excel_buffer.getvalue()
        
        st.download_button(
            label="📥 Export Shortage Report to Excel",
            data=excel_data,
            file_name="stagewise_shortage_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="export_shortages"
        )

# ----------------- TAB 1: SUMMARY REPORT & EXCEL DOWNLOAD -----------------
with tcf_tabs[0]:
    st.markdown("### 📊 Paint Shop Float Summary")
    st.markdown("""
        This report displays the paint shop buffer status by stage and model, matching the exact layout of the paint shop tracker sheet.
    """)
    
    if float_df is not None and not float_df.empty:
        # Map product names to internal TCF models
        def get_summary_product_to_model(prod_name):
            prod = str(prod_name).strip().upper()
            if 'HORNBILL' in prod:
                return 'PUNCH'
            elif 'NOVA' in prod:
                return 'PUNCH.EV'
            elif 'ETURNA' in prod:
                return 'HARRIER.EV'
            elif 'GRAVITAS' in prod:
                return 'SAFARI'
            elif 'Q5' in prod:
                return 'HARRIER'
            elif 'TAYRONA' in prod:
                return 'SAFARI.EV'
            return 'UNKNOWN'
            
        def get_row_paint_stage(row):
            return ae.get_detailed_paint_summary_stage(row)
                
        temp_float_df = float_df.copy()
        temp_float_df['Model_Mapped'] = temp_float_df['PRODUCT'].apply(get_summary_product_to_model)
        temp_float_df['Stage'] = temp_float_df.apply(get_row_paint_stage, axis=1)
        
        stages_list = [
            'PBS FLOAT', 
            'PBS TO POLISHING', 
            'POLISHING TO TOPCOAT', 
            'TOPCOAT TO WETSANDING G ROOFBLACK', 
            'TOPCOAT TO WETSANDING G FRESH', 
            'WETSANDING G TO SEALANT', 
            'PT ENTRY TO SEALANT', 
            'BIW LIFTING G TO PT', 
            'PT BYPASS'
        ]
        
        tcf1_models = ['PUNCH', 'PUNCH.EV']
        tcf2_models = ['HARRIER.EV', 'SAFARI', 'HARRIER', 'SAFARI.EV']
        
        rows = []
        
        # TCF1 Line
        tcf1_sub_df = temp_float_df[temp_float_df['SHOP'] == 'TCF1']
        for model in tcf1_models:
            model_df = tcf1_sub_df[tcf1_sub_df['Model_Mapped'] == model]
            today_vin = len(tcf1_drops[tcf1_drops['Model'] == model]) if tcf1_drops is not None and not tcf1_drops.empty else 0
            
            row_data = {
                'Paint Float': 'TCF1',
                'MODEL': model,
                'Today VIN': today_vin
            }
            
            total_float = 0
            for stage in stages_list:
                cnt = len(model_df[model_df['Stage'] == stage])
                row_data[stage] = cnt
                total_float += cnt
                
            row_data['TOTAL FLOAT'] = total_float
            row_data['TOTAL UPTO SEALANT'] = (
                row_data['PBS FLOAT'] + 
                row_data['PBS TO POLISHING'] + 
                row_data['POLISHING TO TOPCOAT'] + 
                row_data['TOPCOAT TO WETSANDING G ROOFBLACK'] + 
                row_data['TOPCOAT TO WETSANDING G FRESH'] + 
                row_data['WETSANDING G TO SEALANT']
            )
            rows.append(row_data)
            
        # TCF1 TOTAL
        tcf1_subtotal = {
            'Paint Float': 'TCF1',
            'MODEL': 'TCF1 TOTAL',
            'Today VIN': sum(r['Today VIN'] for r in rows if r['Paint Float'] == 'TCF1')
        }
        for col in ['TOTAL FLOAT'] + stages_list + ['TOTAL UPTO SEALANT']:
            tcf1_subtotal[col] = sum(r[col] for r in rows if r['Paint Float'] == 'TCF1')
        rows.append(tcf1_subtotal)
        
        # TCF2 Line
        tcf2_sub_df = temp_float_df[temp_float_df['SHOP'] == 'TCF2']
        tcf2_rows_start_idx = len(rows)
        for model in tcf2_models:
            model_df = tcf2_sub_df[tcf2_sub_df['Model_Mapped'] == model]
            today_vin = len(tcf2_drops[tcf2_drops['Model'] == model]) if tcf2_drops is not None and not tcf2_drops.empty else 0
            
            row_data = {
                'Paint Float': 'TCF2',
                'MODEL': model,
                'Today VIN': today_vin
            }
            
            total_float = 0
            for stage in stages_list:
                cnt = len(model_df[model_df['Stage'] == stage])
                row_data[stage] = cnt
                total_float += cnt
                
            row_data['TOTAL FLOAT'] = total_float
            row_data['TOTAL UPTO SEALANT'] = (
                row_data['PBS FLOAT'] + 
                row_data['PBS TO POLISHING'] + 
                row_data['POLISHING TO TOPCOAT'] + 
                row_data['TOPCOAT TO WETSANDING G ROOFBLACK'] + 
                row_data['TOPCOAT TO WETSANDING G FRESH'] + 
                row_data['WETSANDING G TO SEALANT']
            )
            rows.append(row_data)
            
        # TCF2 TOTAL
        tcf2_subtotal = {
            'Paint Float': 'TCF2',
            'MODEL': 'TCF2 TOTAL',
            'Today VIN': sum(r['Today VIN'] for r in rows[tcf2_rows_start_idx:] if r['Paint Float'] == 'TCF2')
        }
        for col in ['TOTAL FLOAT'] + stages_list + ['TOTAL UPTO SEALANT']:
            tcf2_subtotal[col] = sum(r[col] for r in rows[tcf2_rows_start_idx:] if r['Paint Float'] == 'TCF2')
        rows.append(tcf2_subtotal)
        
        # GRAND TOTAL
        grand_total = {
            'Paint Float': '',
            'MODEL': 'GRAND TOTAL',
            'Today VIN': tcf1_subtotal['Today VIN'] + tcf2_subtotal['Today VIN']
        }
        for col in ['TOTAL FLOAT'] + stages_list + ['TOTAL UPTO SEALANT']:
            grand_total[col] = tcf1_subtotal[col] + tcf2_subtotal[col]
        rows.append(grand_total)
        
        summary_df = pd.DataFrame(rows)
        
        # Rename columns to match user copy perfectly
        display_col_mapping = {
            'Paint Float': 'Paint Float',
            'MODEL': 'MODEL',
            'TOTAL FLOAT': 'TOTAL FLOAT',
            'PBS FLOAT': 'PBS FLOAT',
            'PBS TO POLISHING': 'PBS TO POLISHING',
            'POLISHING TO TOPCOAT': 'POLISHING TO TOPCOAT',
            'TOPCOAT TO WETSANDING G ROOFBLACK': 'TOPCOAT TO WETSANDING G ROOFBLACK',
            'TOPCOAT TO WETSANDING G FRESH': 'TOPCOAT TO WETSANDING G FRESH',
            'WETSANDING G TO SEALANT': 'WETSANDING G TO SEALANT',
            'TOTAL UPTO SEALANT': 'TOTAL UPTO SEALANT',
            'PT ENTRY TO SEALANT': 'PT ENTRY TO SEALANT',
            'BIW LIFTING G TO PT': 'BIW LIFTING G TO PT',
            'PT BYPASS': 'PT BYPASS',
            'Today VIN': 'Today VIN'
        }
        
        summary_df = summary_df[[
            'Paint Float', 'MODEL', 'TOTAL FLOAT', 'PBS FLOAT', 'PBS TO POLISHING',
            'POLISHING TO TOPCOAT', 'TOPCOAT TO WETSANDING G ROOFBLACK',
            'TOPCOAT TO WETSANDING G FRESH', 'WETSANDING G TO SEALANT',
            'TOTAL UPTO SEALANT', 'PT ENTRY TO SEALANT', 'BIW LIFTING G TO PT',
            'PT BYPASS', 'Today VIN'
        ]].rename(columns=display_col_mapping)
        
        # Helper to generate beautiful wrapped HTML table for summary float report
        is_dark_theme = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'
        
        def render_html_float_summary(df, is_dark):
            th_bg = "#1F2937" if is_dark else "#F3F4F6"
            th_text = "#FAFAFA" if is_dark else "#374151"
            td_border = "#30363D" if is_dark else "#E5E7EB"
            text_color = "#FAFAFA" if is_dark else "#111827"
            
            html = f"""
            <div style="overflow-x: auto; border: 1px solid {td_border}; border-radius: 12px; margin-bottom: 2rem; background-color: {'#161B22' if is_dark else '#FFFFFF'}; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
            <table style="width: 100%; border-collapse: collapse; font-family: 'Inter', sans-serif; font-size: 12px; color: {text_color};">
                <thead>
                    <tr style="background-color: {th_bg}; border-bottom: 2px solid {td_border};">
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: left; color: {th_text}; font-weight: 600;">Paint Float</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: left; color: {th_text}; font-weight: 600; width: 110px;">MODEL</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 60px; word-wrap: break-word; white-space: normal;">TOTAL FLOAT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 60px; word-wrap: break-word; white-space: normal;">PBS FLOAT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 80px; word-wrap: break-word; white-space: normal;">PBS TO POLISHING</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 80px; word-wrap: break-word; white-space: normal;">POLISHING TO TOPCOAT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 100px; max-width: 120px; word-wrap: break-word; white-space: normal;">TOPCOAT TO WETSANDING G ROOFBLACK</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 100px; max-width: 120px; word-wrap: break-word; white-space: normal;">TOPCOAT TO WETSANDING G FRESH</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 100px; max-width: 120px; word-wrap: break-word; white-space: normal;">WETSANDING G TO SEALANT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 80px; max-width: 100px; word-wrap: break-word; white-space: normal;">TOTAL UPTO SEALANT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 80px; max-width: 100px; word-wrap: break-word; white-space: normal;">PT ENTRY TO SEALANT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 80px; max-width: 100px; word-wrap: break-word; white-space: normal;">BIW LIFTING G TO PT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 60px; word-wrap: break-word; white-space: normal;">PT BYPASS</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 60px; word-wrap: break-word; white-space: normal;">Today VIN</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for idx_r, row_r in df.iterrows():
                model_val = str(row_r.get('MODEL', '')).strip()
                
                row_bg = "transparent"
                row_text = text_color
                font_weight = "normal"
                
                if 'TOTAL' in model_val and 'GRAND' not in model_val:
                    row_bg = "#3b1f3c" if is_dark else "#f2dcdb"
                    row_text = "#f2dcdb" if is_dark else "#5c1d1b"
                    font_weight = "bold"
                elif 'GRAND TOTAL' in model_val:
                    row_bg = "#4a3f00" if is_dark else "#ffffc5"
                    row_text = "#ffff00" if is_dark else "#806000"
                    font_weight = "bold"
                    
                html += f'<tr style="background-color: {row_bg}; color: {row_text}; font-weight: {font_weight}; border-bottom: 1px solid {td_border};">'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: left;">{row_r.get("Paint Float", "")}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: left;">{row_r.get("MODEL", "")}</td>'
                
                for col in ['TOTAL FLOAT', 'PBS FLOAT', 'PBS TO POLISHING', 'POLISHING TO TOPCOAT', 
                            'TOPCOAT TO WETSANDING G ROOFBLACK', 'TOPCOAT TO WETSANDING G FRESH', 
                            'WETSANDING G TO SEALANT', 'TOTAL UPTO SEALANT', 'PT ENTRY TO SEALANT', 
                            'BIW LIFTING G TO PT', 'PT BYPASS', 'Today VIN']:
                    val = row_r.get(col, 0)
                    val_str = str(val) if pd.notna(val) else "0"
                    html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{val_str}</td>'
                html += '</tr>'
                
            html += """
                </tbody>
            </table>
            </div>
            """
            return html
            
        # Display the first table (wrapped nicely in HTML)
        st.markdown(render_html_float_summary(summary_df, is_dark_theme), unsafe_allow_html=True)
        
        # ----------------- ENGINE & BATTERY REQUIREMENT SUMMARY REPORT -----------------
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("### 📊 Engine & Battery Requirement Summary")
        st.markdown("""
            This report summarizes raw engine inventory status against paint shop float and computes clear-to-build requirements.
        """)
        
        # Compute dictionary values for engines
        engine_stocks_dict = {}
        engine_ta_dict = {}
        if 'engine_df' in st.session_state and st.session_state.engine_df is not None:
            for idx, r_eng in st.session_state.engine_df.iterrows():
                p_no = str(r_eng['Engine Part No']).strip()
                engine_stocks_dict[p_no] = int(r_eng.get('Clearance After 6:30AM', 0))
                engine_ta_dict[p_no] = str(r_eng.get('TA Code', '—')).strip()
                
        # Create mapping dictionary from Short Vehicle Code -> Engine
        vc_to_engine = {}
        if bom_df is not None and not bom_df.empty:
            vc_to_engine = dict(zip(bom_df['Short Vehicle Code'].astype(str).str.strip(), bom_df['Engine'].astype(str).str.strip()))
            
        # Today VIN per engine part
        today_vin_dict = {}
        if tcf1_drops is not None and not tcf1_drops.empty:
            if 'Engine_Part' not in tcf1_drops.columns:
                tcf1_drops['Engine_Part'] = tcf1_drops['VEHICLE CODE'].astype(str).str.strip().str[:9].map(vc_to_engine)
            for part in tcf1_drops['Engine_Part'].dropna().unique():
                p_str = str(part).strip()
                today_vin_dict[p_str] = today_vin_dict.get(p_str, 0) + len(tcf1_drops[tcf1_drops['Engine_Part'] == part])
        if tcf2_drops is not None and not tcf2_drops.empty:
            if 'Engine_Part' not in tcf2_drops.columns:
                tcf2_drops['Engine_Part'] = tcf2_drops['VEHICLE CODE'].astype(str).str.strip().str[:9].map(vc_to_engine)
            for part in tcf2_drops['Engine_Part'].dropna().unique():
                p_str = str(part).strip()
                today_vin_dict[p_str] = today_vin_dict.get(p_str, 0) + len(tcf2_drops[tcf2_drops['Engine_Part'] == part])
                
        # Float demands per engine part
        pbs_float_dict = {}
        upto_sealant_dict = {}
        total_float_dict = {}
        
        stages_upto_sealant = [
            'PBS FLOAT', 
            'PBS TO POLISHING', 
            'POLISHING TO TOPCOAT', 
            'TOPCOAT TO WETSANDING G ROOFBLACK', 
            'TOPCOAT TO WETSANDING G FRESH', 
            'WETSANDING G TO SEALANT'
        ]
        
        temp_float_df['Engine_Part'] = temp_float_df['VEHICLE CODE'].astype(str).str.strip().str[:9].map(vc_to_engine)
        for idx, row_f in temp_float_df.iterrows():
            part = row_f['Engine_Part']
            if pd.isna(part):
                continue
            p_str = str(part).strip()
            stage = row_f['Stage']
            
            total_float_dict[p_str] = total_float_dict.get(p_str, 0) + 1
            if stage == 'PBS FLOAT':
                pbs_float_dict[p_str] = pbs_float_dict.get(p_str, 0) + 1
            if stage in stages_upto_sealant:
                upto_sealant_dict[p_str] = upto_sealant_dict.get(p_str, 0) + 1
                
        # Build TCF1 rows
        punch_parts = [
            ("54850000PTP001", "Punch MT SA"),
            ("54850000PTP002", "Punch AMT SA"),
            ("54970000PTP002", "Punch TC MCE"),
            ("54970000PTP003", "Punch MCE MT"),
            ("54970000PTP004", "Punch MCE AMT"),
            ("54970000PTP005", "Punch MCE CNG MT"),
            ("54970000PTP031", "Punch MCE CNG AMT")
        ]
        
        table2_rows = []
        for part, model in punch_parts:
            clearance = engine_stocks_dict.get(part, 0)
            today_vin = today_vin_dict.get(part, 0)
            bal = clearance - today_vin
            pbs = pbs_float_dict.get(part, 0)
            sealant = upto_sealant_dict.get(part, 0)
            total = total_float_dict.get(part, 0)
            table2_rows.append({
                'Engine Part No': part,
                'Model': model,
                'TA Code': engine_ta_dict.get(part, '—'),
                'Clearance After 6:30AM': clearance,
                'Today VIN': today_vin,
                'Bal': bal,
                'PBS FLOAT': pbs,
                'Float UPTO SEALANT': sealant,
                'TOTAL FLOAT': total,
                'With respect to PBS FLOAT': bal - pbs,
                'With respect to Sealant FLOAT': bal - sealant,
                'With respect to Total FLOAT': bal - total,
                'Type': 'row'
            })
            
        subtotal_1_2 = {
            'Engine Part No': '',
            'Model': '1.2 Lit Total',
            'TA Code': '',
            'Clearance After 6:30AM': '',
            'Today VIN': sum(r['Today VIN'] for r in table2_rows),
            'Bal': '',
            'PBS FLOAT': sum(r['PBS FLOAT'] for r in table2_rows),
            'Float UPTO SEALANT': sum(r['Float UPTO SEALANT'] for r in table2_rows),
            'TOTAL FLOAT': sum(r['TOTAL FLOAT'] for r in table2_rows),
            'With respect to PBS FLOAT': '',
            'With respect to Sealant FLOAT': '',
            'With respect to Total FLOAT': '',
            'Type': 'subtotal'
        }
        table2_rows.append(subtotal_1_2)
        
        # Nova
        part_nova = "546816111212"
        model_nova = "Nova"
        clearance_nova = engine_stocks_dict.get(part_nova, 0)
        today_vin_nova = today_vin_dict.get(part_nova, 0)
        bal_nova = clearance_nova - today_vin_nova
        pbs_nova = pbs_float_dict.get(part_nova, 0)
        sealant_nova = upto_sealant_dict.get(part_nova, 0)
        total_nova = total_float_dict.get(part_nova, 0)
        row_nova = {
            'Engine Part No': part_nova,
            'Model': model_nova,
            'TA Code': engine_ta_dict.get(part_nova, '—'),
            'Clearance After 6:30AM': clearance_nova,
            'Today VIN': today_vin_nova,
            'Bal': bal_nova,
            'PBS FLOAT': pbs_nova,
            'Float UPTO SEALANT': sealant_nova,
            'TOTAL FLOAT': total_nova,
            'With respect to PBS FLOAT': bal_nova - pbs_nova,
            'With respect to Sealant FLOAT': bal_nova - sealant_nova,
            'With respect to Total FLOAT': bal_nova - total_nova,
            'Type': 'row'
        }
        table2_rows.append(row_nova)
        
        # TCF1 Grand Total
        tcf1_grand = {
            'Engine Part No': '',
            'Model': 'TCF1',
            'TA Code': '',
            'Clearance After 6:30AM': '',
            'Today VIN': subtotal_1_2['Today VIN'] + row_nova['Today VIN'],
            'Bal': '',
            'PBS FLOAT': subtotal_1_2['PBS FLOAT'] + row_nova['PBS FLOAT'],
            'Float UPTO SEALANT': subtotal_1_2['Float UPTO SEALANT'] + row_nova['Float UPTO SEALANT'],
            'TOTAL FLOAT': subtotal_1_2['TOTAL FLOAT'] + row_nova['TOTAL FLOAT'],
            'With respect to PBS FLOAT': '',
            'With respect to Sealant FLOAT': '',
            'With respect to Total FLOAT': '',
            'Type': 'total'
        }
        table2_rows.append(tcf1_grand)
        
        # Build TCF2 rows
        tcf2_parts = [
            ("572900000118", "Harrier / Safari Diesel AT"),
            ("572900000120", "Harrier / Safari Diesel MT"),
            ("54780000PTP001", "Harrier / Safari Petrol TGDI MT"),
            ("54780000PTP002", "Harrier / Safari Petrol TGDI AT")
        ]
        
        tcf2_start_idx = len(table2_rows)
        for part, model in tcf2_parts:
            clearance = engine_stocks_dict.get(part, 0)
            today_vin = today_vin_dict.get(part, 0)
            bal = clearance - today_vin
            pbs = pbs_float_dict.get(part, 0)
            sealant = upto_sealant_dict.get(part, 0)
            total = total_float_dict.get(part, 0)
            table2_rows.append({
                'Engine Part No': part,
                'Model': model,
                'TA Code': engine_ta_dict.get(part, '—'),
                'Clearance After 6:30AM': clearance,
                'Today VIN': today_vin,
                'Bal': bal,
                'PBS FLOAT': pbs,
                'Float UPTO SEALANT': sealant,
                'TOTAL FLOAT': total,
                'With respect to PBS FLOAT': bal - pbs,
                'With respect to Sealant FLOAT': bal - sealant,
                'With respect to Total FLOAT': bal - total,
                'Type': 'row'
            })
            
        subtotal_2_0 = {
            'Engine Part No': '',
            'Model': '2 Lit Total',
            'TA Code': '',
            'Clearance After 6:30AM': '',
            'Today VIN': sum(r['Today VIN'] for r in table2_rows[tcf2_start_idx:]),
            'Bal': '',
            'PBS FLOAT': sum(r['PBS FLOAT'] for r in table2_rows[tcf2_start_idx:]),
            'Float UPTO SEALANT': sum(r['Float UPTO SEALANT'] for r in table2_rows[tcf2_start_idx:]),
            'TOTAL FLOAT': sum(r['TOTAL FLOAT'] for r in table2_rows[tcf2_start_idx:]),
            'With respect to PBS FLOAT': '',
            'With respect to Sealant FLOAT': '',
            'With respect to Total FLOAT': '',
            'Type': 'subtotal'
        }
        table2_rows.append(subtotal_2_0)
        
        # Harrier EV
        part_hev = "547380400103"
        model_hev = "Harrier EV"
        clearance_hev = engine_stocks_dict.get(part_hev, 0)
        today_vin_hev = today_vin_dict.get(part_hev, 0)
        bal_hev = clearance_hev - today_vin_hev
        pbs_hev = pbs_float_dict.get(part_hev, 0)
        sealant_hev = upto_sealant_dict.get(part_hev, 0)
        total_hev = total_float_dict.get(part_hev, 0)
        row_hev = {
            'Engine Part No': part_hev,
            'Model': model_hev,
            'TA Code': engine_ta_dict.get(part_hev, '—'),
            'Clearance After 6:30AM': clearance_hev,
            'Today VIN': today_vin_hev,
            'Bal': bal_hev,
            'PBS FLOAT': pbs_hev,
            'Float UPTO SEALANT': sealant_hev,
            'TOTAL FLOAT': total_hev,
            'With respect to PBS FLOAT': bal_hev - pbs_hev,
            'With respect to Sealant FLOAT': bal_hev - sealant_hev,
            'With respect to Total FLOAT': bal_hev - total_hev,
            'Type': 'row'
        }
        table2_rows.append(row_hev)
        
        # TCF2 Grand Total
        tcf2_grand = {
            'Engine Part No': '',
            'Model': 'TCF2',
            'TA Code': '',
            'Clearance After 6:30AM': '',
            'Today VIN': subtotal_2_0['Today VIN'] + row_hev['Today VIN'],
            'Bal': '',
            'PBS FLOAT': subtotal_2_0['PBS FLOAT'] + row_hev['PBS FLOAT'],
            'Float UPTO SEALANT': subtotal_2_0['Float UPTO SEALANT'] + row_hev['Float UPTO SEALANT'],
            'TOTAL FLOAT': subtotal_2_0['TOTAL FLOAT'] + row_hev['TOTAL FLOAT'],
            'With respect to PBS FLOAT': '',
            'With respect to Sealant FLOAT': '',
            'With respect to Total FLOAT': '',
            'Type': 'total'
        }
        table2_rows.append(tcf2_grand)
        
        # Render Table 2 in beautiful HTML with rowspan/colspan
        def render_html_table_2(rows, is_dark):
            th_bg = "#1F2937" if is_dark else "#F3F4F6"
            th_text = "#FAFAFA" if is_dark else "#374151"
            td_border = "#30363D" if is_dark else "#E5E7EB"
            text_color = "#FAFAFA" if is_dark else "#111827"
            
            clearance_bg = "#1b4d32" if is_dark else "#d8f3e5"
            clearance_text = "#FAFAFA" if is_dark else "#1b4d32"
            
            bal_bg = "#4a274c" if is_dark else "#f2dcdb"
            bal_text = "#FAFAFA" if is_dark else "#5c1d1b"
            
            alert_bg = "#5c1d1d" if is_dark else "#ffd1d1"
            alert_text = "#FAFAFA" if is_dark else "#5c1d1d"
            
            html = f"""
            <div style="overflow-x: auto; border: 1px solid {td_border}; border-radius: 12px; margin-bottom: 2rem; background-color: {'#161B22' if is_dark else '#FFFFFF'}; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
            <table style="width: 100%; border-collapse: collapse; font-family: 'Inter', sans-serif; font-size: 12px; color: {text_color};">
                <thead>
                    <tr style="background-color: {th_bg}; border-bottom: 1px solid {td_border};">
                        <th rowspan="2" style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; vertical-align: middle;">Engine / Battery Part No</th>
                        <th rowspan="2" style="padding: 10px 8px; border: 1px solid {td_border}; text-align: left; color: {th_text}; font-weight: 600; width: 180px; vertical-align: middle;">Model</th>
                        <th rowspan="2" style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; vertical-align: middle;">TA Code</th>
                        <th rowspan="2" style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 80px; white-space: normal; vertical-align: middle;">Clearance After 6:30AM</th>
                        <th rowspan="2" style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; vertical-align: middle;">Today VIN</th>
                        <th rowspan="2" style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; background-color: {bal_bg}; color: {bal_text}; vertical-align: middle;">Bal</th>
                        <th colspan="3" style="padding: 6px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600;">Paint Float</th>
                        <th colspan="3" style="padding: 6px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600;">Engine & Battery requirement</th>
                    </tr>
                    <tr style="background-color: {th_bg}; border-bottom: 2px solid {td_border};">
                        <th style="padding: 6px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600;">PBS FLOAT</th>
                        <th style="padding: 6px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600;">Float UPTO SEALANT</th>
                        <th style="padding: 6px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600;">TOTAL FLOAT</th>
                        <th style="padding: 6px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 90px; white-space: normal;">With respect to PBS FLOAT</th>
                        <th style="padding: 6px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 90px; white-space: normal;">With respect to Sealant FLOAT</th>
                        <th style="padding: 6px; border: 1px solid {td_border}; text-align: center; color: {th_text}; font-weight: 600; min-width: 90px; white-space: normal;">With respect to Total FLOAT</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for r_data in rows:
                r_type = r_data['Type']
                
                row_bg = "transparent"
                row_text = text_color
                font_weight = "normal"
                
                if r_type == 'subtotal':
                    row_bg = "#005b8a" if is_dark else "#00B0F0"
                    row_text = "#FFFFFF"
                    font_weight = "bold"
                elif r_type == 'total':
                    row_bg = "#7f7f00" if is_dark else "#ffff00"
                    row_text = "#FAFAFA" if is_dark else "#000000"
                    font_weight = "bold"
                    
                html += f'<tr style="background-color: {row_bg}; color: {row_text}; font-weight: {font_weight}; border-bottom: 1px solid {td_border};">'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r_data["Engine Part No"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: left;">{r_data["Model"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r_data["TA Code"]}</td>'
                
                val_clearance = r_data["Clearance After 6:30AM"]
                if val_clearance != "" and r_type == 'row':
                    html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center; background-color: {clearance_bg}; color: {clearance_text}; font-weight: bold;">{val_clearance}</td>'
                else:
                    html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{val_clearance}</td>'
                    
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r_data["Today VIN"]}</td>'
                
                val_bal = r_data["Bal"]
                if val_bal != "" and r_type == 'row':
                    html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center; background-color: {bal_bg}; color: {bal_text}; font-weight: bold;">{val_bal}</td>'
                else:
                    html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{val_bal}</td>'
                    
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r_data["PBS FLOAT"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r_data["Float UPTO SEALANT"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r_data["TOTAL FLOAT"]}</td>'
                
                for col_k in ["With respect to PBS FLOAT", "With respect to Sealant FLOAT", "With respect to Total FLOAT"]:
                    val_req = r_data[col_k]
                    if val_req != "" and r_type == 'row':
                        if isinstance(val_req, (int, float)) and val_req < 0:
                            html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center; background-color: {alert_bg}; color: {alert_text}; font-weight: bold;">{val_req}</td>'
                        else:
                            html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{val_req}</td>'
                    else:
                        html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{val_req}</td>'
                        
                html += '</tr>'
            html += """
                </tbody>
            </table>
            </div>
            """
            return html
            
        st.markdown(render_html_table_2(table2_rows, is_dark_theme), unsafe_allow_html=True)
        
        # ----------------- COCKPIT & WIRING SHORTAGE REPORTS (EXACT USER FORMAT) -----------------
        st.markdown("---")
        st.markdown("### 🧩 Cockpit & Wiring Shortage Reports")
        st.markdown("""
            These reports track Cockpit and Wiring Harness shortage requirements in the exact layout matching engine summary sheet models.
        """)
        
        # Helper to build shortage table for Cockpit or Front Wiring
        def build_formatted_shortage_table(part_col_name, stock_tcf1, stock_tcf2, bom_df, float_df, tcf1_drops, tcf2_drops):
            if bom_df is None or bom_df.empty:
                return pd.DataFrame()
                
            local_engine_to_model = {}
            local_engine_to_line = {}
            if 'engine_df' in st.session_state and not st.session_state.engine_df.empty:
                local_engine_to_model = dict(zip(st.session_state.engine_df['Engine Part No'].astype(str).str.strip(), st.session_state.engine_df['Model']))
                local_engine_to_line = dict(zip(st.session_state.engine_df['Engine Part No'].astype(str).str.strip(), st.session_state.engine_df['TCF Line']))
            else:
                local_engine_to_model = {item['Engine Part No']: item['Model'] for item in engine_default_data}
                local_engine_to_line = {item['Engine Part No']: item['TCF Line'] for item in engine_default_data}

            vc_to_part = dict(zip(bom_df['Short Vehicle Code'].astype(str).str.strip(), bom_df[part_col_name].astype(str).str.strip()))
            
            part_to_models = {}
            part_to_line = {}
            
            for idx, row in bom_df.iterrows():
                eng = str(row.get('Engine', '')).strip()
                part = str(row.get(part_col_name, '')).strip()
                mdl = local_engine_to_model.get(eng, '')
                line = local_engine_to_line.get(eng, '')
                if mdl and part and part not in ['None', 'nan', '0']:
                    part_to_models.setdefault(part, set()).add(mdl)
                    if line:
                        part_to_line[part] = line
                        
            pbs_dict = {}
            sealant_dict = {}
            total_dict = {}
            stages_upto_sealant = ['PBS FLOAT', 'PBS TO POLISHING', 'POLISHING TO TOPCOAT', 'TOPCOAT TO WETSANDING G ROOFBLACK', 'TOPCOAT TO WETSANDING G FRESH', 'WETSANDING G TO SEALANT']
            
            if float_df is not None and not float_df.empty:
                for idx, row in float_df.iterrows():
                    vc = str(row.get('VEHICLE CODE', '')).strip()[:9]
                    p = vc_to_part.get(vc)
                    if p and p not in ['None', 'nan', '0']:
                        total_dict[p] = total_dict.get(p, 0) + 1
                        stg = row.get('Stage', '')
                        if stg == 'PBS FLOAT':
                            pbs_dict[p] = pbs_dict.get(p, 0) + 1
                        if stg in stages_upto_sealant:
                            sealant_dict[p] = sealant_dict.get(p, 0) + 1
                            
            today_vin_dict = {}
            if tcf1_drops is not None and not tcf1_drops.empty:
                mapped_1 = tcf1_drops['VEHICLE CODE'].astype(str).str.strip().str[:9].map(vc_to_part)
                for p, count in mapped_1.value_counts().items():
                    if pd.notna(p): today_vin_dict[str(p)] = today_vin_dict.get(str(p), 0) + count
                    
            if tcf2_drops is not None and not tcf2_drops.empty:
                mapped_2 = tcf2_drops['VEHICLE CODE'].astype(str).str.strip().str[:9].map(vc_to_part)
                for p, count in mapped_2.value_counts().items():
                    if pd.notna(p): today_vin_dict[str(p)] = today_vin_dict.get(str(p), 0) + count

            table_rows = []
            header_part_name = 'Cockpit Part Number' if 'Cockpit' in part_col_name else 'Wiring Part Number'
            
            stk_1 = stock_tcf1 if stock_tcf1 is not None else {}
            stk_2 = stock_tcf2 if stock_tcf2 is not None else {}

            for part, mdls in part_to_models.items():
                line = part_to_line.get(part, 'TCF1')
                stock_dict = stk_1 if line == 'TCF1' else stk_2
                if stock_dict and part not in stock_dict:
                    continue

                stock = stock_dict.get(part, 0)
                today_vin = today_vin_dict.get(part, 0)
                pbs = pbs_dict.get(part, 0)
                sealant = sealant_dict.get(part, 0)
                total = total_dict.get(part, 0)
                
                sh_pbs = stock - today_vin - pbs
                sh_sealant = stock - today_vin - sealant
                sh_total = stock - today_vin - total
                
                # Filter to include ONLY items with an actual shortage (negative against float)
                if sh_pbs < 0 or sh_sealant < 0 or sh_total < 0:
                    table_rows.append({
                        header_part_name: part,
                        'Model': ', '.join(sorted(mdls)),
                        'LINE': line,
                        'Clearance After 6:30AM': stock,
                        'Today VIN': today_vin,
                        'Paint TOTAL FLOAT': total,
                        'PBS FLOAT': pbs,
                        'Cabs Float UPTO SEALANT': sealant,
                        'Shortage PBS FLOAT': sh_pbs,
                        'Shortage Upto Sealant': sh_sealant,
                        'Shortage TOTAL FLOAT': sh_total
                    })
                
            return pd.DataFrame(table_rows)

        df_cpt_shortage = build_formatted_shortage_table('Cockpit', tcf1_cockpit_start, tcf2_cockpit_start, bom_df, temp_float_df, tcf1_drops, tcf2_drops)
        df_wir_shortage = build_formatted_shortage_table('Front Wiring', tcf1_wiring_start, tcf2_wiring_start, bom_df, temp_float_df, tcf1_drops, tcf2_drops)

        def render_html_formatted_shortage(df, part_header_name, is_dark):
            if df.empty:
                return "<p style='color: #6B7280; font-style: italic;'>No data available.</p>"
                
            th_bg_orange = "#382315" if is_dark else "#FCE4D6"
            th_text_orange = "#FAFAFA" if is_dark else "#73330D"
            
            th_bg_blue = "#1A2B4C" if is_dark else "#BDD7EE"
            th_text_blue = "#FAFAFA" if is_dark else "#1A2B4C"

            th_bg_blue2 = "#1E3A5F" if is_dark else "#9BC2E6"
            
            td_border = "#30363D" if is_dark else "#E5E7EB"
            text_color = "#FAFAFA" if is_dark else "#111827"
            
            alert_bg = "#5c1d1d" if is_dark else "#FFD1D1"
            alert_text = "#FAFAFA" if is_dark else "#5C1D1B"
            
            html = f"""
            <div style="overflow-x: auto; border: 1px solid {td_border}; border-radius: 12px; margin-bottom: 2rem; background-color: {'#161B22' if is_dark else '#FFFFFF'}; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
            <table style="width: 100%; border-collapse: collapse; font-family: 'Inter', sans-serif; font-size: 12px; color: {text_color};">
                <thead>
                    <tr style="border-bottom: 2px solid {td_border};">
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_orange}; color: {th_text_orange}; font-weight: bold;">{part_header_name}</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: left; background-color: {th_bg_orange}; color: {th_text_orange}; font-weight: bold; width: 220px;">Model</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_orange}; color: {th_text_orange}; font-weight: bold;">LINE</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_blue}; color: {th_text_blue}; font-weight: bold;">Clearance After 6:30AM</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_blue}; color: {th_text_blue}; font-weight: bold;">Today VIN</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_blue}; color: {th_text_blue}; font-weight: bold;">Paint TOTAL FLOAT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_blue}; color: {th_text_blue}; font-weight: bold;">PBS FLOAT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_blue}; color: {th_text_blue}; font-weight: bold;">Cabs Float UPTO SEALANT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_blue2}; color: {th_text_blue}; font-weight: bold;">Shortage PBS FLOAT</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_blue2}; color: {th_text_blue}; font-weight: bold;">Shortage Upto Sealant</th>
                        <th style="padding: 10px 8px; border: 1px solid {td_border}; text-align: center; background-color: {th_bg_blue2}; color: {th_text_blue}; font-weight: bold;">Shortage TOTAL FLOAT</th>
                    </tr>
                </thead>
                <tbody>
            """
            for idx, r in df.iterrows():
                html += f'<tr style="border-bottom: 1px solid {td_border};">'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center; font-weight: 600;">{r[part_header_name]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: left;">{r["Model"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r["LINE"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r["Clearance After 6:30AM"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r["Today VIN"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r["Paint TOTAL FLOAT"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r["PBS FLOAT"]}</td>'
                html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{r["Cabs Float UPTO SEALANT"]}</td>'
                
                for col_sh in ["Shortage PBS FLOAT", "Shortage Upto Sealant", "Shortage TOTAL FLOAT"]:
                    val_sh = r[col_sh]
                    if isinstance(val_sh, (int, float)) and val_sh < 0:
                        html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center; background-color: {alert_bg}; color: {alert_text}; font-weight: bold;">{val_sh}</td>'
                    else:
                        html += f'<td style="padding: 8px; border: 1px solid {td_border}; text-align: center;">{val_sh}</td>'
                        
                html += '</tr>'
            html += "</tbody></table></div>"
            return html

        st.markdown("#### 🚗 Cockpit Shortage Report")
        st.markdown(render_html_formatted_shortage(df_cpt_shortage, "Cockpit Part Number", is_dark_theme), unsafe_allow_html=True)

        st.markdown("#### ⚡ Wiring Harness Shortage Report")
        st.markdown(render_html_formatted_shortage(df_wir_shortage, "Wiring Part Number", is_dark_theme), unsafe_allow_html=True)
        
        # Excel generator with beautiful color schemes matching attached copy
        import io
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        import openpyxl.utils
        
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            # Sheet 1: Summary Report
            summary_df.to_excel(writer, index=False, sheet_name='Summary Report')
            workbook = writer.book
            worksheet = writer.sheets['Summary Report']
            
            font_header = Font(name='Calibri', size=11, bold=True, color='000000')
            fill_header = PatternFill(start_color='FCE4D6', end_color='FCE4D6', fill_type='solid') # Peach
            
            font_subtotal = Font(name='Calibri', size=11, bold=True, color='000000')
            fill_subtotal = PatternFill(start_color='F2DCDB', end_color='F2DCDB', fill_type='solid') # Pink/Lavender
            
            font_grand_total = Font(name='Calibri', size=11, bold=True, color='000000')
            fill_grand_total = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid') # Yellow
            
            font_normal = Font(name='Calibri', size=11, color='000000')
            
            thin_border = Border(
                left=Side(style='thin', color='BFBFBF'),
                right=Side(style='thin', color='BFBFBF'),
                top=Side(style='thin', color='BFBFBF'),
                bottom=Side(style='thin', color='BFBFBF')
            )
            
            for col_idx in range(1, len(summary_df.columns) + 1):
                cell = worksheet.cell(row=1, column=col_idx)
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                cell.border = thin_border
                
            for row_idx in range(2, len(summary_df) + 2):
                model_val = str(worksheet.cell(row=row_idx, column=2).value).strip()
                is_subtotal = 'TOTAL' in model_val and 'GRAND' not in model_val
                is_grand = 'GRAND TOTAL' in model_val
                
                for col_idx in range(1, len(summary_df.columns) + 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    
                    if is_subtotal:
                        cell.font = font_subtotal
                        cell.fill = fill_subtotal
                    elif is_grand:
                        cell.font = font_grand_total
                        cell.fill = fill_grand_total
                    else:
                        cell.font = font_normal
                        
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)
                
            worksheet.row_dimensions[1].height = 28
            for row_idx in range(2, len(summary_df) + 2):
                worksheet.row_dimensions[row_idx].height = 20
                
            # Sheet 2: Engine & Battery Requirement Summary
            worksheet2 = workbook.create_sheet('Engine & Battery Requirement')
            worksheet2.row_dimensions[1].height = 25
            worksheet2.row_dimensions[2].height = 25
            
            worksheet2.merge_cells('A1:A2')
            worksheet2.merge_cells('B1:B2')
            worksheet2.merge_cells('C1:C2')
            worksheet2.merge_cells('D1:D2')
            worksheet2.merge_cells('E1:E2')
            worksheet2.merge_cells('F1:F2')
            worksheet2.merge_cells('G1:I1')
            worksheet2.merge_cells('J1:L1')
            
            worksheet2['A1'] = "Engine / Battery Part No"
            worksheet2['B1'] = "Model"
            worksheet2['C1'] = "TA Code"
            worksheet2['D1'] = "Clearance After 6:30AM"
            worksheet2['E1'] = "Today VIN"
            worksheet2['F1'] = "Bal"
            worksheet2['G1'] = "Paint Float"
            worksheet2['J1'] = "Engine & Battery requirement"
            
            worksheet2['G2'] = "PBS FLOAT"
            worksheet2['H2'] = "Float UPTO SEALANT"
            worksheet2['I2'] = "TOTAL FLOAT"
            worksheet2['J2'] = "With respect to PBS FLOAT"
            worksheet2['K2'] = "With respect to Sealant FLOAT"
            worksheet2['L2'] = "With respect to Total FLOAT"
            
            for r in [1, 2]:
                for c in range(1, 13):
                    cell = worksheet2.cell(row=r, column=c)
                    cell.font = font_header
                    if r == 1 and c == 6:
                        cell.fill = PatternFill(start_color='F2DCDB', end_color='F2DCDB', fill_type='solid') # Purple/Pink
                    else:
                        cell.fill = fill_header
                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    cell.border = thin_border
                    
            for r_idx, row_d in enumerate(table2_rows, start=3):
                worksheet2.row_dimensions[r_idx].height = 20
                row_type = row_d['Type']
                
                fill_row = None
                font_row = font_normal
                
                if row_type == 'subtotal':
                    fill_row = PatternFill(start_color='00B0F0', end_color='00B0F0', fill_type='solid') # Blue
                    font_row = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
                elif row_type == 'total':
                    fill_row = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid') # Yellow
                    font_row = Font(name='Calibri', size=11, bold=True, color='000000')
                    
                columns_list = [
                    'Engine Part No', 'Model', 'TA Code', 'Clearance After 6:30AM',
                    'Today VIN', 'Bal', 'PBS FLOAT', 'Float UPTO SEALANT', 'TOTAL FLOAT',
                    'With respect to PBS FLOAT', 'With respect to Sealant FLOAT', 'With respect to Total FLOAT'
                ]
                
                for c_idx, col_key in enumerate(columns_list, start=1):
                    cell = worksheet2.cell(row=r_idx, column=c_idx)
                    val = row_d[col_key]
                    cell.value = val
                    cell.border = thin_border
                    cell.font = font_row
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    
                    if row_type == 'row':
                        if col_key == 'Clearance After 6:30AM':
                            cell.fill = PatternFill(start_color='D8F3E5', end_color='D8F3E5', fill_type='solid')
                            cell.font = Font(name='Calibri', size=11, bold=True, color='1B4D32')
                        elif col_key == 'Bal':
                            cell.fill = PatternFill(start_color='F2DCDB', end_color='F2DCDB', fill_type='solid')
                            cell.font = Font(name='Calibri', size=11, bold=True, color='5C1D1B')
                        elif col_key in ['With respect to PBS FLOAT', 'With respect to Sealant FLOAT', 'With respect to Total FLOAT']:
                            if isinstance(val, (int, float)) and val < 0:
                                cell.fill = PatternFill(start_color='FFD1D1', end_color='FFD1D1', fill_type='solid')
                                cell.font = Font(name='Calibri', size=11, bold=True, color='5C1D1B')
                    elif fill_row:
                        cell.fill = fill_row
                        
            for col in worksheet2.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                worksheet2.column_dimensions[col_letter].width = max(max_len + 3, 12)

            # Function to format openpyxl sheet for Cockpit / Wiring Shortage
            def format_openpyxl_shortage_sheet(sheet_name, df_data, part_col_hdr):
                if df_data.empty:
                    return
                df_data.to_excel(writer, index=False, sheet_name=sheet_name)
                ws = writer.sheets[sheet_name]
                ws.row_dimensions[1].height = 28
                
                fill_peach = PatternFill(start_color='FCE4D6', end_color='FCE4D6', fill_type='solid')
                fill_blue = PatternFill(start_color='BDD7EE', end_color='BDD7EE', fill_type='solid')
                fill_blue2 = PatternFill(start_color='9BC2E6', end_color='9BC2E6', fill_type='solid')
                
                for c_i, col_name in enumerate(df_data.columns, start=1):
                    cell = ws.cell(row=1, column=c_i)
                    cell.font = font_header
                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    cell.border = thin_border
                    if c_i <= 3:
                        cell.fill = fill_peach
                    elif c_i <= 8:
                        cell.fill = fill_blue
                    else:
                        cell.fill = fill_blue2
                        
                for r_i, r_val in enumerate(df_data.iterrows(), start=2):
                    ws.row_dimensions[r_i].height = 20
                    row_dict = r_val[1]
                    for c_i, col_name in enumerate(df_data.columns, start=1):
                        cell = ws.cell(row=r_i, column=c_i)
                        val = row_dict[col_name]
                        cell.value = val
                        cell.border = thin_border
                        cell.font = font_normal
                        cell.alignment = Alignment(horizontal='center' if col_name != 'Model' else 'left', vertical='center')
                        
                        if 'Shortage' in col_name and isinstance(val, (int, float)) and val < 0:
                            cell.fill = PatternFill(start_color='FFD1D1', end_color='FFD1D1', fill_type='solid')
                            cell.font = Font(name='Calibri', size=11, bold=True, color='5C1D1B')
                            
                for col in ws.columns:
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = openpyxl.utils.get_column_letter(col[0].column)
                    ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

            format_openpyxl_shortage_sheet('Cockpit Shortage', df_cpt_shortage, 'Cockpit Part Number')
            format_openpyxl_shortage_sheet('Wiring Shortage', df_wir_shortage, 'Wiring Part Number')
                
        excel_data = excel_buffer.getvalue()
        
        st.download_button(
            label="📥 Export Summary Reports to Excel",
            data=excel_data,
            file_name="paint_shop_float_and_requirements_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="export_summary_report"
        )
    else:
        st.info("Please load Paint Float data in the Control Panel to view the summary report.")
