"""
Configuration management for the TCF PPC Dashboard.
"""
import sys
import os
import streamlit as st

# Ensure we can import from the project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import data_loader as dl

def _ensure_config_loaded():
    """Ensure that the configuration is loaded into session state."""
    if '_config' not in st.session_state:
        # Load all metadata once
        try:
            if hasattr(dl, 'get_all_metadata'):
                st.session_state._config = dl.get_all_metadata()
            else:
                st.session_state._config = {}
        except Exception as e:
            st.error(f"Error loading configuration: {e}")
            st.session_state._config = {}

def get_config(key: str, default=None):
    """
    Get a configuration value.
    
    Args:
        key (str): The configuration key.
        default: The default value if the key is not found.
        
    Returns:
        The configuration value.
    """
    _ensure_config_loaded()
    return st.session_state._config.get(key, default)

def set_config(key: str, value):
    """
    Set a configuration value and write it through to the database via data_loader.
    
    Args:
        key (str): The configuration key.
        value: The configuration value.
    """
    _ensure_config_loaded()
    st.session_state._config[key] = value
    
    # Write through to the database
    try:
        dl.save_metadata(key, value)
    except Exception as e:
        st.error(f"Failed to save configuration for {key}: {e}")
