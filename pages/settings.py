import streamlit as st
import sys
import os

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from core.config import get_config, set_config
except ImportError:
    # Fallback placeholder if core.config is incomplete
    if 'mock_db_config' not in st.session_state:
        st.session_state.mock_db_config = {
            "theme": "Light",
            "onedrive_url": "",
            "sync_interval": 15,
            "engine_stock_target": 100,
            "nova_stock_target": 50
        }
        
    def get_config(key, default=None):
        return st.session_state.mock_db_config.get(key, default)
        
    def set_config(key, value):
        st.session_state.mock_db_config[key] = value

def render():
    """Render the Settings/Control Panel page."""
    st.title("Settings & Control Panel")
    
    st.markdown("Configure application settings, sync intervals, and inventory targets.")
    
    # 1. Appearance / Theme Configuration
    st.header("Appearance")
    current_theme = get_config("theme", "Light")
    theme_options = ["Light", "Dark", "System Default"]
    theme_idx = theme_options.index(current_theme) if current_theme in theme_options else 0
    
    new_theme = st.selectbox("Application Theme", options=theme_options, index=theme_idx)
    if new_theme != current_theme:
        set_config("theme", new_theme)
        st.success(f"Theme updated to {new_theme}")

    st.divider()

    # 2. Sync Configuration
    st.header("Data Integration")
    current_url = get_config("onedrive_url", "")
    new_url = st.text_input("OneDrive Share URL", value=current_url, help="URL for syncing external data.")
    if new_url != current_url:
        set_config("onedrive_url", new_url)
        st.success("OneDrive URL updated.")

    current_sync = get_config("sync_interval", 15)
    new_sync = st.number_input("Sync Interval (minutes)", min_value=1, max_value=1440, value=current_sync)
    if new_sync != current_sync:
        set_config("sync_interval", new_sync)
        st.success(f"Sync interval updated to {new_sync} minutes.")

    st.divider()

    # 3. Inventory Targets Configuration
    st.header("Inventory Targets")
    col1, col2 = st.columns(2)
    
    with col1:
        current_engine = get_config("engine_stock_target", 100)
        new_engine = st.number_input("Engine Stock Target", min_value=0, value=current_engine)
        if new_engine != current_engine:
            set_config("engine_stock_target", new_engine)
            st.success("Engine stock target updated.")
            
    with col2:
        current_nova = get_config("nova_stock_target", 50)
        new_nova = st.number_input("Nova Stock Target", min_value=0, value=current_nova)
        if new_nova != current_nova:
            set_config("nova_stock_target", new_nova)
            st.success("Nova stock target updated.")
