import streamlit as st
import pandas as pd
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from core.data_manager import get_dashboard_data
except ImportError:
    st.error("Failed to import core modules. Application structure is broken.")

def render():
    classified_files = st.session_state.get("classified_files", {})
    st.title("PPC Production Control Tower")

    # Fetch dashboard data
    try:
        data = get_dashboard_data(classified_files)
    except Exception as e:
        import traceback
        st.error(f"Error executing get_dashboard_data:\n\n```text\n{traceback.format_exc()}\n```")
        return

    if data.status == "error":
        st.error(f"🔴 NO VALID DATA AVAILABLE\n\n{data.error_message}")
        return
    elif data.status == "warning":
        st.warning(f"⚠ DATA REFRESH FAILED\n\nShowing last successful dataset.\n\nError: {data.error_message}")
    
    # KPIs from allocations and float
    tcf1_alloc = data.tcf1_alloc_df
    tcf2_alloc = data.tcf2_alloc_df
    combined_alloc = pd.concat([tcf1_alloc, tcf2_alloc], ignore_index=True) if not tcf1_alloc.empty or not tcf2_alloc.empty else pd.DataFrame()
    
    total_pbs = len(combined_alloc) if not combined_alloc.empty else (len(data.float_df[data.float_df['PBS LIFT'].notna()]) if not data.float_df.empty and 'PBS LIFT' in data.float_df.columns else 0)
    
    if not combined_alloc.empty and 'STATUS' in combined_alloc.columns:
        status_series = combined_alloc['STATUS'].astype(str)
        pbs_ready = len(combined_alloc[status_series.str.contains('Ready', na=False)])
        pbs_blocked = len(combined_alloc[status_series.str.contains('Blocked|Unknown|BOM Incomplete|Shortage', na=False)])
        readiness = round((pbs_ready / total_pbs) * 100, 1) if total_pbs > 0 else 0
    else:
        pbs_ready = 0
        pbs_blocked = 0
        readiness = 0

    st.subheader("PBS STATUS")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("PBS FLOAT", total_pbs)
    with c2: st.metric("READY", pbs_ready)
    with c3: st.metric("BLOCKED", pbs_blocked)
    with c4: st.metric("READINESS %", f"{readiness}%")
    
    st.divider()
    
    st.subheader("MATERIAL EXCEPTIONS")
    # Using real metrics
    shortages = data.shortage_report
    engine_shortages = 0
    cockpit_shortages = 0
    wiring_shortages = 0
    
    if not shortages.empty and 'Aggregate Type' in shortages.columns and 'Status' in shortages.columns:
        short_rows = shortages[shortages['Status'].astype(str).str.contains('Shortage', na=False)]
        if not short_rows.empty and 'Net Balance' in short_rows.columns:
            engine_shortages = abs(short_rows[short_rows['Aggregate Type'] == 'Engine']['Net Balance'].sum())
            cockpit_shortages = abs(short_rows[short_rows['Aggregate Type'] == 'Cockpit']['Net Balance'].sum())
            wiring_shortages = abs(short_rows[short_rows['Aggregate Type'] == 'Front Wiring']['Net Balance'].sum())
        
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1: st.metric("ENGINE", int(engine_shortages))
    with mc2: st.metric("COCKPIT", int(cockpit_shortages))
    with mc3: st.metric("WIRING", int(wiring_shortages))
    with mc4: st.metric("MODEL", 0) # Model shortages

    st.divider()

    st.subheader("ACTION REQUIRED")
    actions = []
    if pbs_blocked > 0:
        actions.append(f"🔴 {pbs_blocked} Blocked Cabs")
    if engine_shortages > 0:
        actions.append(f"🟠 {int(engine_shortages)} Engine Shortages")
    if cockpit_shortages > 0:
        actions.append(f"🟠 {int(cockpit_shortages)} Cockpit Shortages")
    
    if not actions:
        st.success("✅ No critical actions required.")
    else:
        for a in actions:
            st.warning(a)
