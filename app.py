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
db_theme = dl.load_metadata('theme', '☀️ White Theme')
if 'theme' not in st.session_state:
    st.session_state.theme = db_theme

# Set page config
st.set_page_config(
    page_title="PBS Clear-to-Build Dashboard",
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
        dl.save_metadata('theme', theme_option)
        st.rerun()

is_dark = st.session_state.theme == "🌙 Dark Theme"

# Inject style blocks dynamically
if is_dark:
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        
        /* Force Dark background globally */
        .stApp {
            background-color: #0F172A !important;
            color: #F1F5F9 !important;
        }
        
        /* Completely hide sidebar and collapse button */
        [data-testid="stSidebar"], section[data-testid="stSidebar"] {
            display: none !important;
            width: 0px !important;
        }
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        .stApp [data-testid="stHeader"] {
            left: 0px !important;
            background-color: transparent !important;
        }
        .main .block-container {
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 100% !important;
        }
        
        .card-ready {
            background-color: #064E3B !important;
            border-left: 4px solid #10B981 !important;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
            color: #D1FAE5 !important;
        }
        
        .card-blocked {
            background-color: #7F1D1D !important;
            border-left: 4px solid #EF4444 !important;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
            color: #FEE2E2 !important;
        }
        
        /* Premium Metric Cards with Custom Accent Colors */
        div[data-testid="stMetric"] {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            padding: 1rem 1.25rem !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-4px) !important;
            box-shadow: 0 12px 24px -8px rgba(0, 0, 0, 0.6) !important;
            border-color: #475569 !important;
        }
        
        /* Apply colorful accents to each metric column */
        div[data-testid="column"]:nth-of-type(1) div[data-testid="stMetric"] {
            border-left: 5px solid #6366F1 !important; /* Indigo */
        }
        div[data-testid="column"]:nth-of-type(2) div[data-testid="stMetric"] {
            border-left: 5px solid #06B6D4 !important; /* Cyan */
        }
        div[data-testid="column"]:nth-of-type(3) div[data-testid="stMetric"] {
            border-left: 5px solid #10B981 !important; /* Emerald */
        }
        div[data-testid="column"]:nth-of-type(4) div[data-testid="stMetric"] {
            border-left: 5px solid #F43F5E !important; /* Rose */
        }
        div[data-testid="column"]:nth-of-type(5) div[data-testid="stMetric"] {
            border-left: 5px solid #A78BFA !important; /* Violet */
        }
        
        div[data-testid="stMetric"] label {
            color: #94A3B8 !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #F8FAFC !important;
            font-weight: 800 !important;
            font-size: 1.8rem !important;
        }
        
        /* Modern segmented control styling for dark tabs */
        div[data-baseweb="tab-list"] {
            background-color: #1E293B !important;
            padding: 0.25rem !important;
            border-radius: 12px !important;
            gap: 6px !important;
            margin-bottom: 1.5rem !important;
        }
        button[data-baseweb="tab"] {
            background-color: transparent !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.6rem 1.2rem !important;
            color: #94A3B8 !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }
        button[data-baseweb="tab"]:hover {
            color: #F8FAFC !important;
            background-color: rgba(255,255,255,0.05) !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background-color: #334155 !important;
            color: #818CF8 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2) !important;
        }
        div[data-baseweb="tab-border"] {
            display: none !important;
        }
        
        /* Expander styling */
        details[data-testid="stExpander"] {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1) !important;
        }
        
        /* Headings */
        h3 {
            color: #F8FAFC !important;
            font-weight: 800 !important;
            letter-spacing: -0.02em;
        }
        
        h4 {
            color: #E2E8F0 !important;
            font-weight: 700 !important;
            letter-spacing: -0.01em;
        }
        
        /* Horizontal rules */
        hr {
            border-color: #334155 !important;
        }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        
        /* Force light/white background globally */
        .stApp {
            background-color: #F8FAFC;
        }
        
        /* Completely hide sidebar and collapse button */
        [data-testid="stSidebar"], section[data-testid="stSidebar"] {
            display: none !important;
            width: 0px !important;
        }
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        .stApp [data-testid="stHeader"] {
            left: 0px !important;
        }
        .main .block-container {
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            max-width: 100% !important;
        }
        
        .card-ready {
            background-color: #F0FAF4;
            border-left: 4px solid #10B981;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        }
        
        .card-blocked {
            background-color: #FFF5F5;
            border-left: 4px solid #EF4444;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        }
        
        /* Premium Metric Cards with Custom Accent Colors */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            padding: 1rem 1.25rem !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-4px) !important;
            box-shadow: 0 12px 20px -8px rgba(0, 0, 0, 0.1), 0 4px 12px -2px rgba(0, 0, 0, 0.04) !important;
            border-color: #CBD5E1 !important;
        }
        
        /* Apply colorful accents to each metric column */
        div[data-testid="column"]:nth-of-type(1) div[data-testid="stMetric"] {
            border-left: 5px solid #4F46E5 !important; /* Indigo */
        }
        div[data-testid="column"]:nth-of-type(2) div[data-testid="stMetric"] {
            border-left: 5px solid #06B6D4 !important; /* Cyan */
        }
        div[data-testid="column"]:nth-of-type(3) div[data-testid="stMetric"] {
            border-left: 5px solid #10B981 !important; /* Emerald */
        }
        div[data-testid="column"]:nth-of-type(4) div[data-testid="stMetric"] {
            border-left: 5px solid #EF4444 !important; /* Rose */
        }
        div[data-testid="column"]:nth-of-type(5) div[data-testid="stMetric"] {
            border-left: 5px solid #8B5CF6 !important; /* Violet */
        }
        
        div[data-testid="stMetric"] label {
            color: #64748B !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #0F172A !important;
            font-weight: 800 !important;
            font-size: 1.8rem !important;
        }
        
        /* Modern segmented control styling for tabs */
        div[data-baseweb="tab-list"] {
            background-color: #F1F5F9 !important;
            padding: 0.25rem !important;
            border-radius: 12px !important;
            gap: 6px !important;
            margin-bottom: 1.5rem !important;
        }
        button[data-baseweb="tab"] {
            background-color: transparent !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.6rem 1.2rem !important;
            color: #475569 !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }
        button[data-baseweb="tab"]:hover {
            color: #0F172A !important;
            background-color: rgba(255,255,255,0.5) !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background-color: #FFFFFF !important;
            color: #4F46E5 !important;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06) !important;
        }
        div[data-baseweb="tab-border"] {
            display: none !important;
        }
        
        /* Expander styling */
        details[data-testid="stExpander"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02);
        }
        
        /* Headings */
        h3 {
            color: #0F172A !important;
            font-weight: 800 !important;
            letter-spacing: -0.02em;
        }
        
        h4 {
            color: #1E293B !important;
            font-weight: 700 !important;
            letter-spacing: -0.01em;
        }
        
        /* Horizontal rules */
        hr {
            border-color: #E2E8F0 !important;
        }
    </style>
    """, unsafe_allow_html=True)

# Render the Title Card
with col_title_card:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #4F46E5 0%, #06B6D4 100%); padding: 1.5rem 2rem; border-radius: 16px; margin-bottom: 2rem; color: white; box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.15), 0 8px 10px -6px rgba(6, 182, 212, 0.15);">
        <h1 style="color: white; font-weight: 850; margin: 0; font-size: 2.1rem; letter-spacing: -0.03em; font-family: 'Inter', sans-serif;">Clear to Build (CTB) Allocation Dashboard</h1>
        <p style="color: rgba(255,255,255,0.95); margin: 0.5rem 0 0 0; font-size: 1rem; font-weight: 400; font-family: 'Inter', sans-serif;">Painted Body Storage (PBS) Buffer Allocation & Multi-Stage Material Availability Summary</p>
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
db_last_reset = dl.load_metadata('last_reset_time')
now = datetime.datetime.now()
reset_threshold = now.replace(hour=6, minute=30, second=0, microsecond=0)

if 'last_reset_time' not in st.session_state:
    if db_last_reset:
        st.session_state.last_reset_time = datetime.datetime.fromisoformat(db_last_reset)
    else:
        st.session_state.last_reset_time = now
        dl.save_metadata('last_reset_time', now.isoformat())

# Load engine stocks from DB or defaults
if 'engine_df' not in st.session_state:
    db_engine_df = dl.load_engine_stocks_from_db()
    if db_engine_df is not None:
        st.session_state.engine_df = db_engine_df
    else:
        st.session_state.engine_df = pd.DataFrame(engine_default_data)

# If now has crossed 6:30 AM today, and last reset was before 6:30 AM today
if now >= reset_threshold and st.session_state.last_reset_time < reset_threshold:
    st.session_state.engine_df = pd.DataFrame(engine_default_data)
    dl.save_engine_stocks_to_db(st.session_state.engine_df)
    st.session_state.last_reset_time = now
    dl.save_metadata('last_reset_time', now.isoformat())
    st.toast("🔄 Shift start auto-reset triggered (6:30 AM). Starting stocks cleared.", icon="🔄")

# Auto-detect file mappings in workspace
workspace_dir = os.path.dirname(os.path.abspath(__file__))
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
        uploaded_files = st.file_uploader(
            "Upload plant reports to replace existing ones",
            accept_multiple_files=True,
            help="Upload raw spreadsheets (Float, Wiring, Cockpit, or VGL). They will automatically replace older files on disk."
        )
        
        # Process uploads immediately, saving to disk and replacing older files
        if uploaded_files:
            uploaded_mappings = dl.classify_files(uploaded_files)
            replaced_any = False
            for category, uploaded_file in uploaded_mappings.items():
                if category == 'BOM':
                    try:
                        parsed_bom = dl.load_bom(uploaded_file)
                        dl.save_bom_to_db(parsed_bom)
                        dl.save_metadata(f"uploaded_{category}", uploaded_file.name)
                        st.toast("💾 Master BOM replaced and saved to database!", icon="💾")
                        replaced_any = True
                    except Exception as e:
                        st.error(f"Failed to parse uploaded BOM: {e}")
                else:
                    # Find old file of same category and delete it
                    old_path = detected_files.get(category)
                    if old_path and os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception as e:
                            st.error(f"Error removing old file: {e}")
                    
                    # Save new file to disk
                    new_path = os.path.join(active_dir, uploaded_file.name)
                    try:
                        with open(new_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        dl.save_metadata(f"uploaded_{category}", uploaded_file.name)
                        st.toast(f"✅ Replaced {category.replace('_',' ')} with {uploaded_file.name}", icon="✅")
                        replaced_any = True
                    except Exception as e:
                        st.error(f"Error saving new file: {e}")
            if replaced_any:
                # Force re-scan and rerun to clear uploader state and refresh
                detected_files = dl.detect_and_classify_files(active_dir)
                st.rerun()
        
        st.markdown("##### Loaded Files Status")
        
        # Check if database has BOM
        db_bom_df = dl.load_bom_from_db()
        
        # Populate loaded_data
        for category in all_categories:
            detected_path = detected_files.get(category)
            is_default_exists = detected_path is not None and os.path.exists(detected_path)
            
            if category == 'BOM':
                if db_bom_df is not None:
                    loaded_data[category] = "DATABASE"
                elif is_default_exists:
                    loaded_data[category] = detected_path
                # Skip status display for BOM as requested
                continue
            
            uploaded_filename = dl.load_metadata(f"uploaded_{category}")
            display_name = category.replace('_',' ').replace('VGL', 'VIN Generation')
            
            if is_default_exists:
                loaded_data[category] = detected_path
                if uploaded_filename and os.path.basename(detected_path) == uploaded_filename:
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
            dl.save_engine_stocks_to_db(edited_engine_df)
            
        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
        if st.button("Reset Clearances to 0 (Shift Start)", type="secondary", use_container_width=True):
            st.session_state.engine_df = pd.DataFrame(engine_default_data)
            dl.save_engine_stocks_to_db(st.session_state.engine_df)
            now_time = datetime.datetime.now()
            st.session_state.last_reset_time = now_time
            dl.save_metadata('last_reset_time', now_time.isoformat())
            # Clear uploaded file registry in metadata
            for cat in all_categories:
                dl.save_metadata(f"uploaded_{cat}", "")
            st.toast("🔄 Engine clearances and upload registries reset!", icon="🔄")
            st.rerun()

core_available = 'BOM' in loaded_data and 'FLOAT_REPORT' in loaded_data

if not core_available:
    st.warning("⚠️ Please ensure the **Master BOM** and **PPC Float Report** are available in the database/workspace or uploaded above to run the dashboard.")
    st.stop()

# ----------------- PARSING & CALCULATING DATA -----------------
try:
    with st.spinner("⏳ Parsing plant reports and running allocation calculations..."):
        # 1. Load BOM
        if loaded_data['BOM'] == 'DATABASE':
            bom_df = dl.load_bom_from_db()
        else:
            bom_df = dl.load_bom(loaded_data['BOM'])
            dl.save_bom_to_db(bom_df)
        
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

except Exception as e:
    st.error(f"❌ Error while running calculations: {e}")
    st.info("Please verify that the uploaded files match the required structure and columns.")
    st.stop()

# ----------------- MAIN PANEL LAYOUT -----------------
# Toggle between TCF1, TCF2, and Combined Summary
tcf_tabs = st.tabs(["🏭 TCF 1 Line (Altroz/Punch/Nova)", "🏭 TCF 2 Line (Harrier/Safari)", "📊 Combined Summary & Material Shortages"])

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

# ----------------- TAB 1: TCF 1 LINE -----------------
with tcf_tabs[0]:
    # KPIs
    ready_count = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '✅ Ready for TCF']) if not tcf1_alloc_df.empty else 0
    blocked_count = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '🚫 Blocked']) if not tcf1_alloc_df.empty else 0
    issue_count = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'].str.startswith('⚠️', na=False)]) if not tcf1_alloc_df.empty else 0
    total_drops = len(tcf1_drops) if tcf1_drops is not None else 0
    
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("VIN Generation", f"{total_drops} cabs", help="Cabs built in TCF1 since shift start")
    kpi_cols[1].metric("PBS Current Stock", f"{len(tcf1_queue)} cabs", help="Active unblocked cabs in TCF1 PBS")
    kpi_cols[2].metric("✅ Ready for TCF", f"{ready_count} cabs", delta=f"+{ready_count} alloc")
    kpi_cols[3].metric("🚫 Blocked (Stock Out)", f"{blocked_count} cabs", delta=f"-{blocked_count} wait", delta_color="inverse")
    kpi_cols[4].metric("⚠️ Data/BOM Issue", f"{issue_count} cabs")
    
    line_subtabs = st.tabs(["📋 FIFO Allocation Queue", "📦 Material Stock Status", "🔍 Bottleneck Parts Analysis"])
    
    # Subtab 1: Queue
    with line_subtabs[0]:
        st.markdown("### TCF1 FIFO Buffer Queue Status")
        if tcf1_alloc_df.empty:
            st.info("No active cabs in TCF1 PBS queue.")
        else:
            # Filter to show only Ready for TCF and Blocked statuses
            filtered_df = tcf1_alloc_df[tcf1_alloc_df['STATUS'].isin(['✅ Ready for TCF', '🚫 Blocked'])].copy()
            
            search_biw = st.text_input("🔍 Quick Search by BIW Number:", key="tcf1_biw_search")
            if search_biw:
                filtered_df = filtered_df[filtered_df['BIW NUMBER'].astype(str).str.contains(search_biw.strip())]
                
            display_cols = ['BIW NUMBER', 'VIN', 'VEHICLE CODE', 'STATUS', 'BLOCKING_REASON', 'PBS LIFT', 'Engine_Part', 'Cockpit_Part', 'Wiring_Part', 'Engine_Stock_After', 'Cockpit_Stock_After', 'Wiring_Stock_After']
            st.dataframe(
                style_alloc_table(filtered_df[display_cols]),
                use_container_width=True,
                hide_index=True
            )
            
    # Subtab 2: Stock
    with line_subtabs[1]:
        st.markdown("### TCF1 Stock Ledger")
        
        # Combine stock counts to display a single table
        # We merge Starting, Consumed, True Current, Allocated (Ready counts), and Final Virtual
        def make_stock_table(start, true, final, consumed, agg_type):
            if start is None or true is None or final is None or consumed is None:
                return pd.DataFrame()
            rows = []
            for part in start.keys():
                st_qty = start.get(part, 0)
                cons_qty = consumed.get(part, 0)
                tc_qty = true.get(part, 0)
                fin_qty = final.get(part, 0)
                alloc_qty = tc_qty - fin_qty
                
                rows.append({
                    "Part Number": part,
                    "Aggregate Type": agg_type,
                    "Shift Start Qty": st_qty,
                    "Consumed (Vin Generation)": cons_qty,
                    "True Current Stock": tc_qty,
                    "Allocated to PBS": alloc_qty,
                    "Post-Alloc Virtual Stock": fin_qty
                })
            return pd.DataFrame(rows)
            
        tcf1_ledger_eng = make_stock_table(engine_stocks_tcf1, true_engine_tcf1, tcf1_final_stocks['engine'] if tcf1_final_stocks['engine'] else {}, eng_cons_tcf1, "Engine")
        tcf1_ledger_ck = make_stock_table(tcf1_cockpit_start, true_cockpit_tcf1, tcf1_final_stocks['cockpit'] if tcf1_final_stocks['cockpit'] else {}, ck_cons_tcf1, "Cockpit")
        tcf1_ledger_wh = make_stock_table(tcf1_wiring_start, true_wiring_tcf1, tcf1_final_stocks['wiring'] if tcf1_final_stocks['wiring'] else {}, wh_cons_tcf1, "Front Wiring")
        
        tcf1_ledger_all = pd.concat([tcf1_ledger_eng, tcf1_ledger_ck, tcf1_ledger_wh], ignore_index=True)
        
        if tcf1_ledger_all.empty:
            st.info("No stock data loaded.")
        else:
            st.dataframe(
                tcf1_ledger_all.style.background_gradient(subset=["Post-Alloc Virtual Stock"], cmap="RdYlGn", vmin=0, vmax=20),
                use_container_width=True,
                hide_index=True
            )
            
            # Stock charts
            st.markdown("---")
            st.markdown("### Stock Availability Profiles")
            chart_cols = st.columns(3)
            
            with chart_cols[0]:
                plot_stock_chart(engine_stocks_tcf1, true_engine_tcf1, tcf1_final_stocks['engine'] if tcf1_final_stocks['engine'] else {}, "Engine Stocks (TCF1)")
            with chart_cols[1]:
                plot_stock_chart(tcf1_cockpit_start, true_cockpit_tcf1, tcf1_final_stocks['cockpit'] if tcf1_final_stocks['cockpit'] else {}, "Cockpit Stocks (TCF1)")
            with chart_cols[2]:
                plot_stock_chart(tcf1_wiring_start, true_wiring_tcf1, tcf1_final_stocks['wiring'] if tcf1_final_stocks['wiring'] else {}, "Wiring Stocks (TCF1)")

    # Subtab 3: Bottleneck Analysis
    with line_subtabs[2]:
        st.markdown("### TCF1 Critical Shortage Bottlenecks")
        if tcf1_alloc_df.empty:
            st.info("No cabs allocated.")
        else:
            blocked_cabs = tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '🚫 Blocked']
            if blocked_cabs.empty:
                st.success("🎉 Zero bottlenecks! All cabs in the buffer queue are Clear-To-Build.")
            else:
                # Extract part numbers from blocking reasons
                blocking_parts = []
                for idx, row in blocked_cabs.iterrows():
                    reason = row['BLOCKING_REASON']
                    # Reason contains part numbers
                    found_parts = re.findall(r'(?:Engine|Cockpit|Wiring)\s+([a-zA-Z0-9_-]+)', reason)
                    blocking_parts.extend(found_parts)
                    
                if blocking_parts:
                    block_counts = pd.Series(blocking_parts).value_counts().reset_index()
                    block_counts.columns = ['Part Number', 'Blocked Cabs Count']
                    
                    st.markdown("#### Parts Causing Most Blockages")
                    st.dataframe(block_counts, use_container_width=True, hide_index=True)
                    
                    # Graph
                    fig, ax = plt.subplots(figsize=(6, 3))
                    fig.patch.set_facecolor('#F8FAFC')
                    ax.set_facecolor('#FFFFFF')
                    ax.bar(block_counts['Part Number'][:5], block_counts['Blocked Cabs Count'][:5], color='#E53E3E', edgecolor='#FFFFFF', linewidth=0.5)
                    ax.tick_params(colors='#374A6B')
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    ax.spines['left'].set_color('#E8ECF1')
                    ax.spines['bottom'].set_color('#E8ECF1')
                    ax.set_title('Top 5 Bottleneck Parts (TCF1)', color='#1B2A4A', fontweight='bold')
                    ax.set_ylabel('Blocked Cabs', color='#374A6B')
                    st.pyplot(fig)
                else:
                    st.info("No specific parts extracted from blocking reasons.")

# ----------------- TAB 2: TCF 2 LINE -----------------
with tcf_tabs[1]:
    # KPIs
    ready_count_tcf2 = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '✅ Ready for TCF']) if not tcf2_alloc_df.empty else 0
    blocked_count_tcf2 = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '🚫 Blocked']) if not tcf2_alloc_df.empty else 0
    issue_count_tcf2 = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'].str.startswith('⚠️', na=False)]) if not tcf2_alloc_df.empty else 0
    total_drops_tcf2 = len(tcf2_drops) if tcf2_drops is not None else 0
    
    kpi_cols_tcf2 = st.columns(5)
    kpi_cols_tcf2[0].metric("VIN Generation", f"{total_drops_tcf2} cabs", help="Cabs built in TCF2 since shift start")
    kpi_cols_tcf2[1].metric("PBS Current Stock", f"{len(tcf2_queue)} cabs", help="Active unblocked cabs in TCF2 PBS")
    kpi_cols_tcf2[2].metric("✅ Ready for TCF", f"{ready_count_tcf2} cabs", delta=f"+{ready_count_tcf2} alloc")
    kpi_cols_tcf2[3].metric("🚫 Blocked (Stock Out)", f"{blocked_count_tcf2} cabs", delta=f"-{blocked_count_tcf2} wait", delta_color="inverse")
    kpi_cols_tcf2[4].metric("⚠️ Data/BOM Issue", f"{issue_count_tcf2} cabs")
    
    line_subtabs_tcf2 = st.tabs(["📋 FIFO Allocation Queue", "📦 Material Stock Status", "🔍 Bottleneck Parts Analysis"])
    
    # Subtab 1: Queue
    with line_subtabs_tcf2[0]:
        st.markdown("### TCF2 FIFO Buffer Queue Status")
        if tcf2_alloc_df.empty:
            st.info("No active cabs in TCF2 PBS queue.")
        else:
            # Filter to show only Ready for TCF and Blocked statuses
            filtered_df_tcf2 = tcf2_alloc_df[tcf2_alloc_df['STATUS'].isin(['✅ Ready for TCF', '🚫 Blocked'])].copy()
            
            search_biw_tcf2 = st.text_input("🔍 Quick Search by BIW Number:", key="tcf2_biw_search")
            if search_biw_tcf2:
                filtered_df_tcf2 = filtered_df_tcf2[filtered_df_tcf2['BIW NUMBER'].astype(str).str.contains(search_biw_tcf2.strip())]
                
            display_cols = ['BIW NUMBER', 'VIN', 'VEHICLE CODE', 'STATUS', 'BLOCKING_REASON', 'PBS LIFT', 'Engine_Part', 'Cockpit_Part', 'Wiring_Part', 'Engine_Stock_After', 'Cockpit_Stock_After', 'Wiring_Stock_After']
            st.dataframe(
                style_alloc_table(filtered_df_tcf2[display_cols]),
                use_container_width=True,
                hide_index=True
            )
            
    # Subtab 2: Stock
    with line_subtabs_tcf2[1]:
        st.markdown("### TCF2 Stock Ledger")
        
        tcf2_ledger_eng = make_stock_table(engine_stocks_tcf2, true_engine_tcf2, tcf2_final_stocks['engine'] if tcf2_final_stocks['engine'] else {}, eng_cons_tcf2, "Engine")
        tcf2_ledger_ck = make_stock_table(tcf2_cockpit_start, true_cockpit_tcf2, tcf2_final_stocks['cockpit'] if tcf2_final_stocks['cockpit'] else {}, ck_cons_tcf2, "Cockpit")
        tcf2_ledger_wh = make_stock_table(tcf2_wiring_start, true_wiring_tcf2, tcf2_final_stocks['wiring'] if tcf2_final_stocks['wiring'] else {}, wh_cons_tcf2, "Front Wiring")
        
        tcf2_ledger_all = pd.concat([tcf2_ledger_eng, tcf2_ledger_ck, tcf2_ledger_wh], ignore_index=True)
        
        if tcf2_ledger_all.empty:
            st.info("No stock data loaded.")
        else:
            st.dataframe(
                tcf2_ledger_all.style.background_gradient(subset=["Post-Alloc Virtual Stock"], cmap="RdYlGn", vmin=0, vmax=20),
                use_container_width=True,
                hide_index=True
            )
            
            # Stock charts
            st.markdown("---")
            st.markdown("### Stock Availability Profiles")
            chart_cols_tcf2 = st.columns(3)
            
            with chart_cols_tcf2[0]:
                plot_stock_chart(engine_stocks_tcf2, true_engine_tcf2, tcf2_final_stocks['engine'] if tcf2_final_stocks['engine'] else {}, "Engine Stocks (TCF2)")
            with chart_cols_tcf2[1]:
                plot_stock_chart(tcf2_cockpit_start, true_cockpit_tcf2, tcf2_final_stocks['cockpit'] if tcf2_final_stocks['cockpit'] else {}, "Cockpit Stocks (TCF2)")
            with chart_cols_tcf2[2]:
                plot_stock_chart(tcf2_wiring_start, true_wiring_tcf2, tcf2_final_stocks['wiring'] if tcf2_final_stocks['wiring'] else {}, "Wiring Stocks (TCF2)")

    # Subtab 3: Bottleneck Analysis
    with line_subtabs_tcf2[2]:
        st.markdown("### TCF2 Critical Shortage Bottlenecks")
        if tcf2_alloc_df.empty:
            st.info("No cabs allocated.")
        else:
            blocked_cabs_tcf2 = tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '🚫 Blocked']
            if blocked_cabs_tcf2.empty:
                st.success("🎉 Zero bottlenecks! All cabs in the buffer queue are Clear-To-Build.")
            else:
                blocking_parts_tcf2 = []
                for idx, row in blocked_cabs_tcf2.iterrows():
                    reason = row['BLOCKING_REASON']
                    found_parts = re.findall(r'(?:Engine|Cockpit|Wiring)\s+([a-zA-Z0-9_-]+)', reason)
                    blocking_parts_tcf2.extend(found_parts)
                    
                if blocking_parts_tcf2:
                    block_counts_tcf2 = pd.Series(blocking_parts_tcf2).value_counts().reset_index()
                    block_counts_tcf2.columns = ['Part Number', 'Blocked Cabs Count']
                    
                    st.markdown("#### Parts Causing Most Blockages")
                    st.dataframe(block_counts_tcf2, use_container_width=True, hide_index=True)
                    
                    # Graph
                    fig, ax = plt.subplots(figsize=(6, 3))
                    fig.patch.set_facecolor('#F8FAFC')
                    ax.set_facecolor('#FFFFFF')
                    ax.bar(block_counts_tcf2['Part Number'][:5], block_counts_tcf2['Blocked Cabs Count'][:5], color='#E53E3E', edgecolor='#FFFFFF', linewidth=0.5)
                    ax.tick_params(colors='#374A6B')
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                    ax.spines['left'].set_color('#E8ECF1')
                    ax.spines['bottom'].set_color('#E8ECF1')
                    ax.set_title('Top 5 Bottleneck Parts (TCF2)', color='#1B2A4A', fontweight='bold')
                    ax.set_ylabel('Blocked Cabs', color='#374A6B')
                    st.pyplot(fig)
                else:
                    st.info("No specific parts extracted from blocking reasons.")

# ----------------- TAB 3: COMBINED SUMMARY & SHORTAGES -----------------
with tcf_tabs[2]:
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
    if pbs_on_hold.empty:
        st.success("🎉 Excellent! No cabs currently on quality hold in the PBS buffer.")
    else:
        st.warning(f"⚠️ {len(pbs_on_hold)} cabs are currently held in PBS and skipped from Clear-to-Build checks.")
        st.dataframe(
            pbs_on_hold[['SR NO', 'BIW NUMBER', 'VIN', 'VEHICLE CODE', 'SHOP', 'HOLD BY', 'REASONS S', 'PBS LIFT']],
            use_container_width=True,
            hide_index=True
        )
        
    st.markdown("---")
    
    # Shortage Report - Stagewise Float
    st.markdown("### 🔮 Shortage Report: Paint Float Stagewise Material Demands")
    st.markdown("""
        This report tracks part requirements for all cabs currently moving through the paint shop stages:
        **BIW LIFTING ➡️ PTCED ➡️ SEALANT ➡️ TOPCOAT ➡️ PBS LIFT**.
        
        * **Stage Demand**: Number of cabs currently in this specific stage requiring the part.
        * **Cumulative Demand**: Total count required by this stage and all downstream stages closer to TCF (e.g. for TOPCOAT, it sums TOPCOAT + PBS requirements).
        * **Net Balance**: True Current Stock minus Cumulative Demand. A negative balance represents a future shortage!
    """)
    
    if shortage_report_df.empty:
        st.info("No stagewise requirements calculated.")
    else:
        # Filter
        selected_stages = st.multiselect(
            "Filter by paint shop stages:",
            options=['1. PBS LIFT', '2. TOPCOAT', '3. SEALANT', '4. PTCED', '5. BIW LIFTING'],
            default=['1. PBS LIFT', '2. TOPCOAT', '3. SEALANT', '4. PTCED', '5. BIW LIFTING'],
            key="stages_filter"
        )
        
        selected_types = st.multiselect(
            "Filter by part category:",
            options=['Engine', 'Cockpit', 'Front Wiring'],
            default=['Engine', 'Cockpit', 'Front Wiring'],
            key="parts_filter"
        )
        
        rep_filtered = shortage_report_df[
            shortage_report_df['Stage'].isin(selected_stages) & 
            shortage_report_df['Aggregate Type'].isin(selected_types)
        ]
        
        # Color coding rows by status
        def style_shortage_table(df):
            if df.empty:
                return df
            is_dark = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'
            
            def get_row_style(row):
                status = row.get('Status')
                if status.startswith('🚫'):
                    if is_dark:
                        return ['background-color: #7F1D1D; color: #FEE2E2'] * len(row)
                    else:
                        return ['background-color: #FFF5F5; color: #B91C1C'] * len(row)
                elif status.startswith('⚠️'):
                    if is_dark:
                        return ['background-color: #334155; color: #94A3B8'] * len(row)
                    else:
                        return ['background-color: #F8FAFC; color: #6B7A99'] * len(row)
                elif status.startswith('🟠'):
                    if is_dark:
                        return ['background-color: #78350F; color: #FEF3C7'] * len(row)
                    else:
                        return ['background-color: #FFFBEB; color: #92400E'] * len(row)
                else:
                    if is_dark:
                        return ['background-color: #064E3B; color: #D1FAE5'] * len(row)
                    else:
                        return ['background-color: #F0FAF4; color: #166534'] * len(row)
            return df.style.apply(get_row_style, axis=1)
            
        st.dataframe(
            style_shortage_table(rep_filtered),
            use_container_width=True,
            hide_index=True
        )
        
        # Display summary of total shortages
        st.markdown("#### Future Material Shortages Summary")
        shortages_only = shortage_report_df[shortage_report_df['Net Balance'] < 0]
        if shortages_only.empty:
            st.success("🎉 No material shortages predicted for any parts across any paint float stages!")
        else:
            # Group by Part Number to find maximum cumulative deficit
            critical_summary = shortages_only.groupby(['Part Number', 'Aggregate Type', 'TCF Line']).agg(
                Max_Deficit=('Net Balance', 'min'),
                Worst_Stage=('Stage', 'last') # Stage furthest back in the flow experiencing shortage
            ).reset_index()
            critical_summary['Max_Deficit'] = critical_summary['Max_Deficit'].abs()
            critical_summary.columns = ['Part Number', 'Aggregate Type', 'TCF Line', 'Shortage Qty Needed', 'Worst Hit Stage']
            st.dataframe(
                critical_summary.style.background_gradient(subset=['Shortage Qty Needed'], cmap='OrRd'),
                use_container_width=True,
                hide_index=True
            )

# ----------------- BOTTOM DATA INTEGRITY REMARKS (Unknown VC / BOM Incomplete) -----------------
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown("### ⚠️ Data Integrity Remarks & Action Items (Missing BOM / Unknown VC)")

# Extract rows with data/BOM issues
data_issues_tcf1 = tcf1_alloc_df[tcf1_alloc_df['STATUS'].isin(['⚠️ Unknown VC', '⚠️ BOM Incomplete'])].copy() if not tcf1_alloc_df.empty else pd.DataFrame()
data_issues_tcf2 = tcf2_alloc_df[tcf2_alloc_df['STATUS'].isin(['⚠️ Unknown VC', '⚠️ BOM Incomplete'])].copy() if not tcf2_alloc_df.empty else pd.DataFrame()

# Standardize columns to match and concatenate
if not data_issues_tcf1.empty:
    data_issues_tcf1['Line'] = 'TCF1'
if not data_issues_tcf2.empty:
    data_issues_tcf2['Line'] = 'TCF2'

combined_issues = pd.concat([data_issues_tcf1, data_issues_tcf2], ignore_index=True)

if combined_issues.empty:
    st.success("🎉 All cabs in the buffer queue have valid Vehicle Codes and complete Master BOM definitions!")
else:
    st.warning(f"⚠️ Found {len(combined_issues)} cabs with missing BOM configurations or unknown Vehicle Codes. Please update the Master BOM database.")
    
    display_cols = ['BIW NUMBER', 'VIN', 'VEHICLE CODE', 'STATUS', 'BLOCKING_REASON', 'Line', 'PBS LIFT']
    
    # Theme-aware coloring for the issues table
    is_dark = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'
    def style_issues_table(df):
        if is_dark:
            return df.style.apply(lambda row: ['background-color: #451a03; color: #fef3c7'] * len(row), axis=1)
        else:
            return df.style.apply(lambda row: ['background-color: #fffbeb; color: #92400E'] * len(row), axis=1)
            
    st.dataframe(
        style_issues_table(combined_issues[display_cols]),
        use_container_width=True,
        hide_index=True
    )
