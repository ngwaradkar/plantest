import streamlit as st
import pandas as pd
import datetime
import os
import io
import report_process
from core.data_manager import get_dashboard_data

def render():
    st.markdown("### 📊 Ageing & Hold Cab Details")
    st.markdown("Overview of stage-wise aging analysis (**BIW → PT**, **PT → PBS**, **PBS buffer**) and quality hold cabs categorized by agency and location from the PPC Float Report.")

    if "aging_holidays" not in st.session_state:
        st.session_state.aging_holidays = []

    classified_files = st.session_state.get('classified_files', {})
    db_data = get_dashboard_data(classified_files)
    float_df = db_data.float_df if db_data else None

    # Control Panel
    default_aging_date = st.session_state.get("aging_analysis_date", datetime.date.today())

    with st.container(border=True):
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.6, 2.6, 1.8])
        with col_ctrl1:
            sel_analysis_date = st.date_input(
                "📅 Analysis Date",
                value=default_aging_date,
                key="pages_quality_analysis_date",
                help="Aging is calculated from stage entry timestamp up to this date."
            )
            st.session_state.aging_analysis_date = sel_analysis_date

        with col_ctrl2:
            st.markdown("<div style='font-size: 13px; font-weight: 600; margin-bottom: 4px;'>🏖️ Holiday Manager (Excluded Days)</div>", unsafe_allow_html=True)
            col_h_input, col_h_add = st.columns([2.5, 1.2])
            with col_h_input:
                new_hol = st.date_input("Add Holiday", value=datetime.date.today(), key="pages_picker_aging_hol", label_visibility="collapsed")
            with col_h_add:
                if st.button("➕ Add", key="pages_btn_add_aging_hol", use_container_width=True):
                    if new_hol not in st.session_state.aging_holidays:
                        st.session_state.aging_holidays.append(new_hol)
                        st.session_state.aging_holidays.sort()
                        st.session_state.pop("aging_results", None)
                        st.rerun()

            if st.session_state.aging_holidays:
                hol_labels = [f"{h.strftime('%d %b')} ({h.strftime('%a')})" for h in sorted(st.session_state.aging_holidays)]
                st.caption(f"**{len(st.session_state.aging_holidays)} Excluded:** {', '.join(hol_labels)}")
                if st.button("🗑️ Clear Holidays", key="pages_btn_clear_aging_hols"):
                    st.session_state.aging_holidays = []
                    st.session_state.pop("aging_results", None)
                    st.rerun()
            else:
                st.caption("No holidays excluded. All calendar days counted.")

        with col_ctrl3:
            st.markdown("<div style='font-size: 13px; font-weight: 600; margin-bottom: 4px;'>⚡ Ageing Engine</div>", unsafe_allow_html=True)
            btn_calc_aging = st.button("🚀 Calculate Ageing", type="primary", use_container_width=True, key="pages_btn_run_aging_calc")

    if btn_calc_aging:
        with st.spinner("⏳ Calculating stage-wise aging and hold cab breakdowns..."):
            try:
                if float_df is not None and not float_df.empty:
                    res_tuple = report_process.process_aging_from_df(
                        float_df,
                        sel_analysis_date,
                        st.session_state.aging_holidays
                    )
                    st.session_state.aging_results = {
                        'excel_bytes': res_tuple[0],
                        'df_biw': res_tuple[1],
                        'df_pt': res_tuple[2],
                        'sum_biw': res_tuple[3],
                        'sum_pt': res_tuple[4],
                        'pbs_excel_bytes': res_tuple[5],
                        'df_pbs': res_tuple[6],
                        'sum_pbs': res_tuple[7],
                        'hold_excel_bytes': res_tuple[8],
                        'df_hold_cabs': res_tuple[9],
                        'analysis_date': sel_analysis_date,
                    }
                    st.toast("✅ Aging & Hold Cab Reports calculated successfully!", icon="📊")
                else:
                    st.error("❌ No Float Report data available.")
            except Exception as e_aging:
                st.error(f"❌ Failed to calculate aging: {e_aging}")

    aging_res = st.session_state.get("aging_results")
    if aging_res is None:
        st.info("💡 Float data is ready. Click **'🚀 Calculate Ageing'** above to generate the full Aging & Hold Cab reports.")
        return

    ad_res       = aging_res['analysis_date']
    df_biw_res   = aging_res['df_biw']
    df_pt_res    = aging_res['df_pt']
    df_pbs_res   = aging_res['df_pbs']
    df_hold_res  = aging_res['df_hold_cabs']
    sum_biw_res  = aging_res['sum_biw']
    sum_pt_res   = aging_res['sum_pt']
    sum_pbs_res  = aging_res['sum_pbs']
    ex_b_res     = aging_res['excel_bytes']
    pbs_ex_b_res = aging_res['pbs_excel_bytes']
    hold_ex_b_res= aging_res['hold_excel_bytes']

    # KPI Metrics
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("🔵 BIW → PT", f"{len(df_biw_res)} cabs")
    m2.metric("🟡 PT → PBS", f"{len(df_pt_res)} cabs")
    m3.metric("🟢 PBS Buffer", f"{len(df_pbs_res)} cabs")
    m4.metric("🔴 Hold Cabs", f"{len(df_hold_res)} cabs")
    m5.metric("📅 Analysis Date", ad_res.strftime("%d %b %Y"))
    m6.metric("🏖️ Holidays Excl.", f"{len(st.session_state.aging_holidays)}")

    st.markdown("<br>", unsafe_allow_html=True)

    # Downloads
    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button(
            label="⬇️ Download Excel (BIW & PT)",
            data=ex_b_res,
            file_name=f"Paint_WBS_Ageing_Analysis_{ad_res.strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="pages_btn_dl_biw_pt_aging"
        )
    with dl2:
        st.download_button(
            label="⬇️ Download PBS Aging Report",
            data=pbs_ex_b_res,
            file_name=f"PBS_Ageing_Report_{ad_res.strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="pages_btn_dl_pbs_aging"
        )
    with dl3:
        st.download_button(
            label="⬇️ Download Hold Cab Report",
            data=hold_ex_b_res,
            file_name=f"Hold_Cab_Report_{ad_res.strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="pages_btn_dl_hold_cabs_report"
        )

    st.markdown("---")

    _BUCKET_HEX = {
        "1 Day": "#E2EFDA",
        "2 to 3 Days": "#FFF2CC",
        "4 To 7 Days": "#FCE4D6",
        "8 to 10 Days": "#F4CCCC",
        "11 to 15 Days": "#EA9999",
        "More than 15 days": "#C00000",
    }
    _BUCKET_WHITE_TXT = {"More than 15 days", "11 to 15 Days"}

    def _fmt_aging_cell(val):
        bg = _BUCKET_HEX.get(str(val), "transparent")
        fg = "#FFFFFF" if str(val) in _BUCKET_WHITE_TXT else "#1E293B"
        return f"background-color: {bg}; color: {fg}; font-weight: 600; border-radius: 4px; padding: 2px 6px;"

    is_dark_curr = st.session_state.get('theme', '☀️ White Theme') == '🌙 Dark Theme'

    def _render_summary_table_html(pivot_data, lift_label):
        bucket_display = {
            "More than 15 days": ">15d",
            "11 to 15 Days": "11–15d",
            "8 to 10 Days": "8–10d",
            "4 To 7 Days": "4–7d",
            "2 to 3 Days": "2–3d",
            "1 Day": "1d",
        }
        hdr_bg = "#1E3A5F" if is_dark_curr else "#1E40AF"
        bdr_col = "#334155" if is_dark_curr else "#CBD5E1"
        cell_bdr = "#334155" if is_dark_curr else "#E2E8F0"
        txt_col = "#E2E8F0" if is_dark_curr else "#1E293B"

        header_cols = "".join(f'<th style="padding: 7px 10px; font-size: 12px; text-align: center; border: 1px solid {bdr_col}; background: {hdr_bg}; color: #FFFFFF;">{bucket_display.get(b, b)}</th>' for b in report_process.BUCKET_ORDER)

        rows_html = ""
        for i, model in enumerate(report_process.MODEL_ORDER):
            row = pivot_data.get(model, {b: 0 for b in report_process.BUCKET_ORDER})
            cells = ""
            for b in report_process.BUCKET_ORDER:
                val = row.get(b, 0)
                cell_val = "–" if val == 0 else str(val)
                cells += f'<td style="padding: 6px 10px; font-size: 13px; text-align: center; border: 1px solid {cell_bdr}; color: {txt_col}; font-weight: {600 if val > 0 else 400};">{cell_val}</td>'
            total = row.get("Total", 0)
            tot_val = "–" if total == 0 else str(total)
            bg = "#1E293B" if (is_dark_curr and i % 2 == 1) else ("#0F172A" if is_dark_curr else ("#F8FAFC" if i % 2 == 1 else "#FFFFFF"))
            rows_html += f'<tr style="background: {bg};"><td style="padding: 6px 12px; font-size: 13px; font-weight: 600; text-align: left; border: 1px solid {cell_bdr}; color: {"#93C5FD" if is_dark_curr else "#1E40AF"};">{model}</td>{cells}<td style="padding: 6px 10px; font-size: 13px; font-weight: 700; text-align: center; border: 1px solid {cell_bdr}; color: {"#FFFFFF" if is_dark_curr else "#0F172A"};">{tot_val}</td></tr>'

        cells = ""
        grand = 0
        for b in report_process.BUCKET_ORDER:
            val = sum(pivot_data.get(m, {}).get(b, 0) for m in report_process.MODEL_ORDER)
            cells += f'<td style="padding: 6px 10px; font-size: 13px; font-weight: 700; text-align: center; border: 1px solid {bdr_col}; color: {"#38BDF8" if is_dark_curr else "#0369A1"};">{val}</td>'
            grand += val
        total_bg = "rgba(14, 165, 233, 0.18)" if is_dark_curr else "#E0F2FE"
        rows_html += f'<tr style="background: {total_bg}; font-weight: 700;"><td style="padding: 7px 12px; font-size: 13px; text-align: left; border: 1px solid {bdr_col}; color: {"#38BDF8" if is_dark_curr else "#0369A1"};">{lift_label}</td>{cells}<td style="padding: 7px 10px; font-size: 14px; text-align: center; border: 1px solid {bdr_col}; color: {"#38BDF8" if is_dark_curr else "#0369A1"};">{grand}</td></tr>'

        empty_cells = "".join(f'<td style="padding: 5px 10px; text-align: center; border: 1px solid {cell_bdr}; color: #94A3B8;">–</td>' for _ in report_process.BUCKET_ORDER)
        jblock_bg = "#111827" if is_dark_curr else "#F1F5F9"
        rows_html += f'<tr style="background: {jblock_bg}; font-style: italic;"><td style="padding: 5px 12px; font-size: 12px; text-align: left; border: 1px solid {cell_bdr}; color: #94A3B8;">J Block</td>{empty_cells}<td style="padding: 5px 10px; font-size: 12px; text-align: center; border: 1px solid {cell_bdr}; color: #94A3B8;">0</td></tr>'

        return f'''
        <div style="overflow-x: auto; margin-bottom: 1.2rem; border-radius: 8px; border: 1px solid {cell_bdr};">
            <table style="width: 100%; border-collapse: collapse; font-family: Inter, sans-serif;">
                <thead>
                    <tr>
                        <th style="padding: 7px 12px; font-size: 12px; text-align: left; border: 1px solid {bdr_col}; background: {hdr_bg}; color: #FFFFFF;">Model</th>
                        {header_cols}
                        <th style="padding: 7px 10px; font-size: 12px; text-align: center; border: 1px solid {bdr_col}; background: {hdr_bg}; color: #FFFFFF;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        '''

    sub_tab_sum, sub_tab_biw, sub_tab_pt, sub_tab_pbs, sub_tab_hold = st.tabs([
        "📊 Summary",
        "🔵 BIW to PT Detail",
        "🟡 PT to PBS Detail",
        "🟢 PBS Detail",
        "🔴 Hold Cab Report"
    ])

    with sub_tab_sum:
        st.markdown("<h4 style='margin-bottom: 6px; color: #0284C7;'>BIW to PT – Age Analysis</h4>", unsafe_allow_html=True)
        st.markdown(_render_summary_table_html(sum_biw_res, "BIW to PT Lift"), unsafe_allow_html=True)

        st.markdown("<h4 style='margin-bottom: 6px; color: #0284C7;'>PT to PBS – Age Analysis</h4>", unsafe_allow_html=True)
        st.markdown(_render_summary_table_html(sum_pt_res, "PT to PBS Lift"), unsafe_allow_html=True)

        st.markdown("<h4 style='margin-bottom: 6px; color: #0284C7;'>PBS – Age Analysis</h4>", unsafe_allow_html=True)
        st.markdown(_render_summary_table_html(sum_pbs_res, "PBS Lift"), unsafe_allow_html=True)

    with sub_tab_biw:
        if df_biw_res.empty:
            st.info("🎉 No vehicles currently in BIW to PT stage.")
        else:
            f1_b, f2_b, f3_b = st.columns(3)
            models_b = ["All"] + sorted([m for m in df_biw_res["MODEL_NAME"].dropna().unique().tolist() if m])
            buckets_b = ["All"] + [b for b in report_process.BUCKET_ORDER if b in df_biw_res["Ageing"].values]
            shops_b = ["All"] + sorted([s for s in df_biw_res["SHOP"].dropna().unique().tolist() if s])

            sel_m_b = f1_b.selectbox("Model Filter:", models_b, key="p_sel_aging_biw_model")
            sel_b_b = f2_b.selectbox("Ageing Bucket Filter:", buckets_b, key="p_sel_aging_biw_bucket")
            sel_s_b = f3_b.selectbox("Shop Filter:", shops_b, key="p_sel_aging_biw_shop")

            view_biw = df_biw_res.copy()
            if sel_m_b != "All": view_biw = view_biw[view_biw["MODEL_NAME"] == sel_m_b]
            if sel_b_b != "All": view_biw = view_biw[view_biw["Ageing"] == sel_b_b]
            if sel_s_b != "All": view_biw = view_biw[view_biw["SHOP"] == sel_s_b]

            cols_map_biw = {
                "SR NO": "Sr No",
                "BIW NUMBER": "BIW Number",
                "MODEL_NAME": "Product",
                "COLOUR": "Colour",
                "SHOP": "Shop",
                "BIW LIFTING": "BIW Lifting",
                "aging_days": "Days",
                "Ageing": "Ageing",
            }
            avail_b = [c for c in cols_map_biw if c in view_biw.columns]
            view_disp_b = view_biw[avail_b].rename(columns=cols_map_biw)
            st.caption(f"Showing **{len(view_disp_b)}** of **{len(df_biw_res)}** records")

            try:
                styled_b = view_disp_b.style.map(_fmt_aging_cell, subset=["Ageing"])
                st.dataframe(styled_b, use_container_width=True, hide_index=True, height=500)
            except Exception:
                st.dataframe(view_disp_b, use_container_width=True, hide_index=True, height=500)

    with sub_tab_pt:
        if df_pt_res.empty:
            st.info("🎉 No vehicles currently in PT to PBS stage.")
        else:
            f1_p, f2_p, f3_p = st.columns(3)
            models_p = ["All"] + sorted([m for m in df_pt_res["MODEL_NAME"].dropna().unique().tolist() if m])
            buckets_p = ["All"] + [b for b in report_process.BUCKET_ORDER if b in df_pt_res["Ageing"].values]
            shops_p = ["All"] + sorted([s for s in df_pt_res["SHOP"].dropna().unique().tolist() if s])

            sel_m_p = f1_p.selectbox("Model Filter:", models_p, key="p_sel_aging_pt_model")
            sel_b_p = f2_p.selectbox("Ageing Bucket Filter:", buckets_p, key="p_sel_aging_pt_bucket")
            sel_s_p = f3_p.selectbox("Shop Filter:", shops_p, key="p_sel_aging_pt_shop")

            view_pt = df_pt_res.copy()
            if sel_m_p != "All": view_pt = view_pt[view_pt["MODEL_NAME"] == sel_m_p]
            if sel_b_p != "All": view_pt = view_pt[view_pt["Ageing"] == sel_b_p]
            if sel_s_p != "All": view_pt = view_pt[view_pt["SHOP"] == sel_s_p]

            cols_map_pt = {
                "SR NO": "Sr No",
                "BIW NUMBER": "BIW Number",
                "MODEL_NAME": "Product",
                "COLOUR": "Colour",
                "SHOP": "Shop",
                "PTCED": "PT Ced",
                "aging_days": "Days",
                "Ageing": "Ageing",
            }
            avail_p = [c for c in cols_map_pt if c in view_pt.columns]
            view_disp_p = view_pt[avail_p].rename(columns=cols_map_pt)
            st.caption(f"Showing **{len(view_disp_p)}** of **{len(df_pt_res)}** records")

            try:
                styled_p = view_disp_p.style.map(_fmt_aging_cell, subset=["Ageing"])
                st.dataframe(styled_p, use_container_width=True, hide_index=True, height=500)
            except Exception:
                st.dataframe(view_disp_p, use_container_width=True, hide_index=True, height=500)

    with sub_tab_pbs:
        if df_pbs_res.empty:
            st.info("🎉 No vehicles currently in PBS stage.")
        else:
            f1_pbs, f2_pbs, f3_pbs = st.columns(3)
            models_pbs = ["All"] + sorted([m for m in df_pbs_res["MODEL_NAME"].dropna().unique().tolist() if m])
            buckets_pbs = ["All"] + [b for b in report_process.BUCKET_ORDER if b in df_pbs_res["Ageing"].values]
            shops_pbs = ["All"] + sorted([s for s in df_pbs_res["SHOP"].dropna().unique().tolist() if s])

            sel_m_pbs = f1_pbs.selectbox("Model Filter:", models_pbs, key="p_sel_aging_pbs_model")
            sel_b_pbs = f2_pbs.selectbox("Ageing Bucket Filter:", buckets_pbs, key="p_sel_aging_pbs_bucket")
            sel_s_pbs = f3_pbs.selectbox("Shop Filter:", shops_pbs, key="p_sel_aging_pbs_shop")

            view_pbs = df_pbs_res.copy()
            if sel_m_pbs != "All": view_pbs = view_pbs[view_pbs["MODEL_NAME"] == sel_m_pbs]
            if sel_b_pbs != "All": view_pbs = view_pbs[view_pbs["Ageing"] == sel_b_pbs]
            if sel_s_pbs != "All": view_pbs = view_pbs[view_pbs["SHOP"] == sel_s_pbs]

            cols_map_pbs = {
                "SR NO": "Sr No",
                "VIN": "VIN",
                "BIW NUMBER": "BIW Number",
                "VEHICLE CODE": "Vehicle Code",
                "MODEL_NAME": "Product",
                "SALES DESCRIPTION": "Sales Description",
                "COLOUR": "Colour",
                "SHOP": "Shop",
                "PBS LIFT": "PBS Lift",
                "HOLD BY": "Hold By",
                "aging_days": "Days",
                "Ageing": "Ageing",
                "Reason_for_aging": "Reason for aging"
            }
            avail_pbs = [c for c in cols_map_pbs if c in view_pbs.columns]
            view_disp_pbs = view_pbs[avail_pbs].rename(columns=cols_map_pbs)
            st.caption(f"Showing **{len(view_disp_pbs)}** of **{len(df_pbs_res)}** records")

            try:
                styled_pbs = view_disp_pbs.style.map(_fmt_aging_cell, subset=["Ageing"])
                st.dataframe(styled_pbs, use_container_width=True, hide_index=True, height=500)
            except Exception:
                st.dataframe(view_disp_pbs, use_container_width=True, hide_index=True, height=500)

    with sub_tab_hold:
        if df_hold_res.empty:
            st.info("🎉 Excellent! No cabs currently on hold between PTCED and PBS stages.")
        else:
            f1_h, f2_h, f3_h = st.columns(3)
            agencies_h = ["All"] + sorted([a for a in df_hold_res["Agency"].dropna().unique().tolist() if a])
            locations_h = ["All"] + sorted([l for l in df_hold_res["Location"].dropna().unique().tolist() if l])
            models_h = ["All"] + sorted([p for p in df_hold_res["PRODUCT"].dropna().unique().tolist() if p])

            sel_a_h = f1_h.selectbox("Agency Filter:", agencies_h, key="p_sel_aging_hold_agency")
            sel_l_h = f2_h.selectbox("Location Filter:", locations_h, key="p_sel_aging_hold_location")
            sel_p_h = f3_h.selectbox("Product Filter:", models_h, key="p_sel_aging_hold_product")

            view_hold = df_hold_res.copy()
            if sel_a_h != "All": view_hold = view_hold[view_hold["Agency"] == sel_a_h]
            if sel_l_h != "All": view_hold = view_hold[view_hold["Location"] == sel_l_h]
            if sel_p_h != "All": view_hold = view_hold[view_hold["PRODUCT"] == sel_p_h]

            cols_map_hold = {
                "SR NO": "Sr No",
                "VIN": "VIN",
                "BIW NUMBER": "BIW No",
                "VEHICLE CODE": "Vehicle Code",
                "PRODUCT": "Product",
                "COLOUR": "Colour",
                "PTCED": "PTCED",
                "PBS LIFT": "PBS Lift",
                "Days": "Days",
                "HOLD BY": "Hold By",
                "Reason": "Reason",
                "Location": "Location",
                "Agency": "Agency",
            }
            avail_h = [c for c in cols_map_hold if c in view_hold.columns]
            view_disp_hold = view_hold[avail_h].rename(columns=cols_map_hold)
            st.caption(f"Showing **{len(view_disp_hold)}** of **{len(df_hold_res)}** hold cabs")
            st.dataframe(view_disp_hold, use_container_width=True, hide_index=True, height=500)
