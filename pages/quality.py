import streamlit as st
import pandas as pd
import datetime
import os
import io
import report_process
from core.data_manager import get_dashboard_data

def render():
    st.markdown("### 🛑 Hold Cab Details")
    st.markdown("Overview and registry of all vehicles currently placed on quality hold in the Paint Shop and PBS buffer, categorized by **Agency**, **Location**, and **Product** from the PPC Float Report.")

    classified_files = st.session_state.get('classified_files', {})
    db_data = get_dashboard_data(classified_files)
    float_df = db_data.float_df if db_data else None

    detected_hold_date = report_process.get_default_analysis_date(float_df, None) or datetime.date.today()

    df_hold_res = None
    hold_ex_b_res = None

    if float_df is not None and not float_df.empty:
        try:
            df_hold_res, hold_ex_b_res = report_process.process_hold_cabs_from_df(
                float_df, analysis_date=detected_hold_date
            )
        except Exception as e_hold:
            st.error(f"❌ Failed to extract hold cabs: {e_hold}")

    if float_df is None or float_df.empty:
        st.info("💡 Please load the PPC Float Report to view Hold Cab Details.")
        return

    if df_hold_res is None or df_hold_res.empty:
        st.success("🎉 Excellent! No vehicles are currently on hold between PTCED and PBS stages.")
        return

    tot_holds = len(df_hold_res)
    paint_holds = len(df_hold_res[df_hold_res["Agency"] == "Paint shop"])
    punch_biw_holds = len(df_hold_res[df_hold_res["Agency"] == "Punch BIW"])
    nova_biw_holds = len(df_hold_res[df_hold_res["Agency"] == "NOVA BIW"])
    biw_holds = punch_biw_holds + nova_biw_holds
    other_holds = len(df_hold_res[~df_hold_res["Agency"].isin(["Paint shop", "Punch BIW", "NOVA BIW"])])
    pbs_loc_holds = len(df_hold_res[df_hold_res["Location"] == "pbs"])
    ps_loc_holds = len(df_hold_res[df_hold_res["Location"] == "paintshop"])

    # KPI Metrics
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("🔴 Total Hold Cabs", f"{tot_holds} cabs")
    m2.metric("🎨 Paint Shop Agency", f"{paint_holds} cabs")
    m3.metric("🏭 BIW Agency", f"{biw_holds} cabs")
    m4.metric("🛑 In PBS Buffer", f"{pbs_loc_holds} cabs")
    m5.metric("🎨 In Paint Stage", f"{ps_loc_holds} cabs")
    m6.metric("📅 Snapshot Date", detected_hold_date.strftime("%d %b %Y"))

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Excel Download Button
    if hold_ex_b_res:
        st.download_button(
            label="⬇️ Download Hold Cab Report (Excel)",
            data=hold_ex_b_res,
            file_name=f"Hold_Cab_Report_{detected_hold_date.strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="pages_btn_dl_hold_cabs_report"
        )

    st.markdown("---")

    # Sub-tabs for Hold Cab organization
    sub_tab_all, sub_tab_paint, sub_tab_biw = st.tabs([
        "📋 All Hold Cabs Registry",
        "🎨 Paint Shop Cabs",
        "🏭 BIW Cabs"
    ])

    from report_process import render_html_hold_cabs_table
    is_dark_curr = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'

    cols_map_hold = {
        "SR NO": "Sr No",
        "BIW NUMBER": "BIW No",
        "PRODUCT": "Product",
        "COLOUR": "Colour",
        "HOLD BY": "Hold By",
        "Reason": "Reason",
        "Location": "Location",
        "Agency": "Agency",
    }

    # Sub-Tab 1: All Hold Cabs Registry with interactive filters
    with sub_tab_all:
        f1_h, f2_h, f3_h, f4_h = st.columns([1.5, 1.5, 1.5, 2.5])
        agencies_h = ["All"] + sorted([a for a in df_hold_res["Agency"].dropna().unique().tolist() if a])
        locations_h = ["All"] + sorted([l for l in df_hold_res["Location"].dropna().unique().tolist() if l])
        models_h = ["All"] + sorted([p for p in df_hold_res["PRODUCT"].dropna().unique().tolist() if p])

        sel_a_h = f1_h.selectbox("Agency Filter:", agencies_h, key="p_sel_hold_all_agency")
        sel_l_h = f2_h.selectbox("Location Filter:", locations_h, key="p_sel_hold_all_location")
        sel_p_h = f3_h.selectbox("Product Filter:", models_h, key="p_sel_hold_all_product")
        search_query = f4_h.text_input("🔍 Search (BIW, Reason, Hold By):", "", key="p_search_hold_all")

        view_all = df_hold_res.copy()
        if sel_a_h != "All": view_all = view_all[view_all["Agency"] == sel_a_h]
        if sel_l_h != "All": view_all = view_all[view_all["Location"] == sel_l_h]
        if sel_p_h != "All": view_all = view_all[view_all["PRODUCT"] == sel_p_h]
        if search_query.strip():
            q = search_query.strip().lower()
            view_all = view_all[
                view_all["BIW NUMBER"].astype(str).str.lower().str.contains(q) |
                view_all["Reason"].astype(str).str.lower().str.contains(q) |
                view_all["HOLD BY"].astype(str).str.lower().str.contains(q)
            ]

        avail_h = [c for c in cols_map_hold if c in view_all.columns]
        view_disp_all = view_all[avail_h].rename(columns=cols_map_hold)
        st.caption(f"Showing **{len(view_disp_all)}** of **{tot_holds}** hold cabs")
        st.markdown(render_html_hold_cabs_table(view_disp_all, is_dark=is_dark_curr), unsafe_allow_html=True)
        with st.expander("📋 View Plain Data Table (Raw Grid)", expanded=False):
            st.dataframe(view_disp_all, use_container_width=True, hide_index=True)

    # Sub-Tab 2: Paint Shop Cabs
    with sub_tab_paint:
        df_paint_cabs = df_hold_res[df_hold_res["Agency"] == "Paint shop"].copy()
        if df_paint_cabs.empty:
            st.info("🎉 No cabs currently on hold under Paint Shop agency.")
        else:
            st.caption(f"Showing **{len(df_paint_cabs)}** Paint Shop hold cabs")
            avail_p = [c for c in cols_map_hold if c in df_paint_cabs.columns]
            view_disp_paint = df_paint_cabs[avail_p].rename(columns=cols_map_hold)
            st.markdown(render_html_hold_cabs_table(view_disp_paint, is_dark=is_dark_curr), unsafe_allow_html=True)
            with st.expander("📋 View Plain Data Table (Raw Grid)", expanded=False):
                st.dataframe(view_disp_paint, use_container_width=True, hide_index=True)

    # Sub-Tab 3: BIW Cabs
    with sub_tab_biw:
        df_biw_cabs = df_hold_res[df_hold_res["Agency"].isin(["Punch BIW", "NOVA BIW"])].copy()
        if df_biw_cabs.empty:
            st.info("🎉 No cabs currently on hold under BIW agencies (Punch BIW / NOVA BIW).")
        else:
            st.caption(f"Showing **{len(df_biw_cabs)}** BIW hold cabs")
            avail_b = [c for c in cols_map_hold if c in df_biw_cabs.columns]
            view_disp_biw = df_biw_cabs[avail_b].rename(columns=cols_map_hold)
            st.markdown(render_html_hold_cabs_table(view_disp_biw, is_dark=is_dark_curr), unsafe_allow_html=True)
            with st.expander("📋 View Plain Data Table (Raw Grid)", expanded=False):
                st.dataframe(view_disp_biw, use_container_width=True, hide_index=True)
