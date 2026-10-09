import streamlit as st

def render_sidebar():
    """
    Renders the professional left sidebar for navigation.
    Uses st.session_state._active_page to navigate.
    """
    with st.sidebar:
        st.title("🏭 Planner Dashboard")
        st.markdown("---")
        
        if "_active_page" not in st.session_state:
            st.session_state._active_page = "Control Tower"

        def nav_button(label: str, icon: str):
            is_active = st.session_state._active_page == label
            button_style = "primary" if is_active else "secondary"
            
            if st.button(f"{icon} {label}", key=f"nav_{label}", use_container_width=True, type=button_style):
                st.session_state._active_page = label
                st.rerun()

        st.subheader("Navigation")
        nav_button("Control Tower", "🗼")
        nav_button("Production", "⚙️")
        nav_button("Material Control", "📦")
        nav_button("Quality", "✅")
        nav_button("Reports", "📊")
        nav_button("Communication", "💬")
        
        st.markdown("---")
        st.info("System Status: Online")
    
    return st.session_state._active_page
