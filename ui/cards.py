import streamlit as st

def render_kpi_card(title: str, value: str, delta: str = None, col: st.delta_generator.DeltaGenerator = None):
    """
    Renders a premium KPI metric card.
    """
    container = col if col else st
    container.metric(label=title, value=value, delta=delta)

def render_action_card(title: str, description: str, action_label: str, on_click=None, key: str = None):
    """
    Renders an action card with a title, description, and a primary button.
    """
    with st.container():
        st.markdown(f"### {title}")
        st.markdown(description)
        if st.button(action_label, type="primary", key=key):
            if on_click:
                on_click()

def render_status_badge(status: str) -> str:
    """
    Returns a markdown string representing a status badge.
    """
    status = str(status).strip().lower()
    if status in ['ready', 'completed', 'success', 'online']:
        color = "var(--success-color)"
        bg = "var(--card-ready-bg)"
        text = "var(--card-ready-text)"
    elif status in ['blocked', 'error', 'failed', 'offline']:
        color = "var(--danger-color)"
        bg = "var(--card-blocked-bg)"
        text = "var(--card-blocked-text)"
    elif status in ['in progress', 'running', 'warning']:
        color = "var(--warning-color)"
        bg = "transparent"
        text = "var(--warning-color)"
    else:
        color = "var(--text-secondary)"
        bg = "transparent"
        text = "var(--text-secondary)"
        
    return f"<span style='background-color: {bg}; color: {text}; border: 1px solid {color}; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;'>{status}</span>"

def render_data_quality_panel(quality_metrics: dict):
    """
    Renders a panel showing data quality metrics.
    """
    st.markdown("### Data Quality")
    if not quality_metrics:
        st.info("No data quality metrics available.")
        return
        
    cols = st.columns(len(quality_metrics))
    for col, (metric_name, metric_val) in zip(cols, quality_metrics.items()):
        col.metric(label=metric_name, value=metric_val)
