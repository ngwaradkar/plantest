import streamlit as st
import os

# Color Constants
PRIMARY_NAVY = '#0F172A'
PRIMARY_BLUE = '#2563EB'
SUCCESS_GREEN = '#10B981'
WARNING_ORANGE = '#F59E0B'
DANGER_RED = '#EF4444'

def apply_theme(is_dark: bool):
    """
    Injects CSS based on the chosen theme.
    """
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

    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "style.css")
    
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
    except FileNotFoundError:
        css_content = ""
        st.error("style.css not found.")

    full_css = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        {theme_vars}
        
        {css_content}
    </style>
    """
    st.markdown(full_css, unsafe_allow_html=True)
