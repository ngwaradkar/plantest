import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import io
from datetime import datetime, timedelta
import pytz
import os
import sys
import time
from streamlit_paste_button import paste_image_button

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import data_loader as dl
import allocation_engine as ae

def render():
    classified_files = st.session_state.get('classified_files', {})
    from core.data_manager import get_dashboard_data
    try:
        data = get_dashboard_data(classified_files)
    except Exception:
        data = None
        
    tcf1_drops = None
    tcf2_drops = None
    tcf1_alloc_df = pd.DataFrame()
    tcf2_alloc_df = pd.DataFrame()
    float_df = pd.DataFrame()
    
    db_folder_path = st.session_state.get('_config', {}).get('db_folder_path', r'C:\PPC_DB')
    try:
        shop_totals, shop_vehicles_df, _ = dl.load_shop_wise_report(db_folder_path)
    except Exception:
        shop_totals, shop_vehicles_df = None, None
    
    if data and data.status != "error":
        alloc_df = pd.DataFrame(data.alloc_results)
        if not alloc_df.empty:
            tcf1_alloc_df = alloc_df[alloc_df.get('SHOP', '') == 'TCF1']
            tcf2_alloc_df = alloc_df[alloc_df.get('SHOP', '') == 'TCF2']
        float_df = data.float_df

    def format_ist_now(fmt='%d-%m-%Y %I:%M %p'):
        from datetime import datetime
        import pytz
        tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(tz).strftime(fmt)

    def get_ist_now():
        from datetime import datetime
        import pytz
        tz = pytz.timezone('Asia/Kolkata')
        return datetime.now(tz)

    def format_ist_nearest_15min(fmt='%d-%m-%Y %I:%M %p'):
        import datetime
        import pytz
        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(tz)
        minute = (now.minute // 15) * 15
        return now.replace(minute=minute, second=0, microsecond=0).strftime(fmt)

    st.markdown("Send live shift production summaries and material shortage alerts directly to Telegram channels, groups, or planners.")

    # Collapsed credentials expander (hidden by default)
    with st.expander("⚙️ Telegram Bot Settings (Click to Edit Token / Chat ID)", expanded=False):
        st.markdown("<small style='color:#8896AB'>Configure Telegram Bot API Key & Target Chat ID</small>", unsafe_allow_html=True)
        
        input_token = st.text_input("Telegram Bot API Token:", value=st.session_state.telegram_token, type="password", key="input_telegram_token")
        input_chat_id = st.text_input("Telegram Chat ID / Group ID:", value=st.session_state.telegram_chat_id, key="input_telegram_chat_id")
        
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        btn_t1, btn_t2 = st.columns(2)
        with btn_t1:
            if st.button("💾 Save Credentials", type="primary", use_container_width=True, key="save_tg_creds_btn"):
                st.session_state.telegram_token = input_token.strip()
                st.session_state.telegram_chat_id = input_chat_id.strip()
                try:
                    dl.save_metadata('telegram_token', input_token.strip())
                    dl.save_metadata('telegram_chat_id', input_chat_id.strip())
                except Exception:
                    pass
                st.toast("💾 Telegram credentials saved to database!", icon="💾")

        with btn_t2:
            if st.button("🧪 Send Test Msg", type="secondary", use_container_width=True, key="test_tg_creds_btn"):
                test_msg = "<b>🤖 TML Planner Dashboard Connected!</b>\n\nTelegram Bot integration successfully verified."
                success, status_lbl = dl.send_telegram_message(input_token.strip(), input_chat_id.strip(), test_msg)
                if success:
                    st.success(status_lbl)
                else:
                    st.error(status_lbl)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("#### 📊 Report Message Preview & Dispatch")
        st.markdown("<small style='color:#8896AB'>Select report type to preview and dispatch via Telegram</small>", unsafe_allow_html=True)

        # Helper function for detailed blocked reasons summary
        def format_blocked_summary(alloc_df):
            if alloc_df is None or alloc_df.empty:
                return "0"
            
            blocked_df = alloc_df[alloc_df['STATUS'].astype(str).str.contains('Blocked|Hold')].copy()
            tot_blocked = len(blocked_df)
            if tot_blocked == 0:
                return "0"
                
            reason_counts = {}
            for idx, r in blocked_df.iterrows():
                reason = str(r.get('BLOCKING_REASON', 'Unspecified')).strip()
                if 'Shortage:' in reason:
                    clean_part = reason.replace('Shortage:', '').split('(')[0].strip()
                    tokens = clean_part.split()
                    if len(tokens) >= 2 and tokens[-1].isdigit():
                        clean_r = " ".join(tokens[:-1])
                    else:
                        clean_r = clean_part
                elif 'Quality' in reason or 'Hold' in reason or 'QA' in reason:
                    clean_r = "QA Hold"
                elif 'BOM' in reason:
                    clean_r = "BOM Incomplete"
                else:
                    clean_r = reason[:20]
                    
                reason_counts[clean_r] = reason_counts.get(clean_r, 0) + 1
                
            breakdown_items = [f"{cnt} {r_lbl}" for r_lbl, cnt in reason_counts.items()]
            breakdown_str = ", ".join(breakdown_items)
            return f"{tot_blocked} ({breakdown_str})"

        # ----------------- REPORT 1: TCF1 & TCF2 PPC PLANNER DASHBOARD REPORT -----------------
        t1_vin_gen = int(tcf1_drops['VIN_Count'].sum()) if (tcf1_drops is not None and not tcf1_drops.empty and 'VIN_Count' in tcf1_drops.columns) else (len(tcf1_drops) if tcf1_drops is not None else 0)
        t2_vin_gen = int(tcf2_drops['VIN_Count'].sum()) if (tcf2_drops is not None and not tcf2_drops.empty and 'VIN_Count' in tcf2_drops.columns) else (len(tcf2_drops) if tcf2_drops is not None else 0)

        t1_ready = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '✅ Ready for TCF']) if not tcf1_alloc_df.empty else 0
        t1_shortages_cnt = len(tcf1_alloc_df[tcf1_alloc_df['STATUS'] == '🚫 Blocked']) if not tcf1_alloc_df.empty else 0
        t1_blocked_summary = format_blocked_summary(tcf1_alloc_df)

        t2_ready = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '✅ Ready for TCF']) if not tcf2_alloc_df.empty else 0
        t2_shortages_cnt = len(tcf2_alloc_df[tcf2_alloc_df['STATUS'] == '🚫 Blocked']) if not tcf2_alloc_df.empty else 0
        t2_blocked_summary = format_blocked_summary(tcf2_alloc_df)

        t1_pbs_total = len(pbs_all[pbs_all['SHOP'] == 'TCF1']) if (float_df is not None and not float_df.empty and 'pbs_all' in locals() and not pbs_all.empty) else len(tcf1_alloc_df)
        t1_qa_hold = len(pbs_on_hold[pbs_on_hold['SHOP'] == 'TCF1']) if ('pbs_on_hold' in locals() and not pbs_on_hold.empty) else 0

        t2_pbs_total = len(pbs_all[pbs_all['SHOP'] == 'TCF2']) if (float_df is not None and not float_df.empty and 'pbs_all' in locals() and not pbs_all.empty) else len(tcf2_alloc_df)
        t2_qa_hold = len(pbs_on_hold[pbs_on_hold['SHOP'] == 'TCF2']) if ('pbs_on_hold' in locals() and not pbs_on_hold.empty) else 0

        # Nova Total Float Qty (124) and Nova Today VIN Qty (30)
        nova_total_float_qty = 0
        if 'paint_summary_dict' in locals() and paint_summary_dict and 'PUNCH.EV' in paint_summary_dict:
            nova_total_float_qty = paint_summary_dict['PUNCH.EV'].get('TOTAL FLOAT', 0)
        elif float_df is not None and not float_df.empty:
            is_nova_mask = (
                float_df['PRODUCT'].astype(str).str.upper().str.contains('NOVA') |
                float_df['VEHICLE CODE'].astype(str).str.startswith('5468')
            )
            nova_total_float_qty = len(float_df[is_nova_mask])

        nova_vin_qty = 0
        if tcf1_drops is not None and not tcf1_drops.empty:
            vin_match_col = 'Model_Family' if 'Model_Family' in tcf1_drops.columns else ('Model' if 'Model' in tcf1_drops.columns else None)
            if vin_match_col:
                nova_drops = tcf1_drops[tcf1_drops[vin_match_col] == 'PUNCH.EV']
            else:
                nova_drops = tcf1_drops[tcf1_drops['VEHICLE CODE'].astype(str).str.startswith('5468')]
            nova_vin_qty = int(nova_drops['VIN_Count'].sum()) if 'VIN_Count' in nova_drops.columns else len(nova_drops)
        elif not tcf1_alloc_df.empty:
            nova_cabs = tcf1_alloc_df[
                tcf1_alloc_df['Model'].astype(str).str.contains('Nova|Punch EV|PUNCH.EV', case=False, na=False, regex=True) |
                tcf1_alloc_df['VEHICLE CODE'].astype(str).str.startswith('5468')
            ]
            nova_vin_qty = len(nova_cabs)
        tcf1_drop_val = 0
        tcf1_paint_val = 0
        tcf2_drop_val = 0
        tcf2_paint_val = 0
        t60_val = 0
        t40_val = 0
        
        if shop_totals:
            tcf1_drop_val = int(shop_totals.get('TCF DROP', 0))
            tcf2_drop_val = int(shop_totals.get('TCF2 DROP', 0))
            t60_val = int(shop_totals.get('T60', 0))
            t40_val = int(shop_totals.get('T40', 0))
            
        if shop_vehicles_df is not None and not shop_vehicles_df.empty:
            tcf1_m = shop_vehicles_df[shop_vehicles_df['Model'].isin(['PUNCH', 'PUNCH Exports', 'PUNCH EV', 'ALTROZ'])]
            tcf2_m = shop_vehicles_df[shop_vehicles_df['Model'].isin(['HARRIER EV', 'SAFARI', 'HARRIER', 'SAFARI EV'])]
            
            if not tcf1_m.empty:
                tcf1_paint_val = int(tcf1_m['Paint Lifting'].sum())
                sum_t60 = int(tcf1_m['T60'].sum())
                if sum_t60 > 0 or t60_val == 0:
                    t60_val = sum_t60
            if not tcf2_m.empty:
                tcf2_paint_val = int(tcf2_m['Paint Lifting'].sum())
                sum_t40 = int(tcf2_m['T40'].sum())
                if sum_t40 > 0 or t40_val == 0:
                    t40_val = sum_t40

        now_str_r1 = format_ist_now("%d-%m-%Y %I:%M %p")
        tg_report_1_text = f"📊 TCF1 & TCF2 PPC REPORT\n"
        tg_report_1_text += f"⏰ Report Time: {now_str_r1}\n\n"
        tg_report_1_text += f"🏭 TCF1 LINE (Punch / Punch EV):\n"
        tg_report_1_text += f" • 🚜 Dropping: {tcf1_drop_val}\n"
        tg_report_1_text += f" • 🎨 Paint Lifting: {tcf1_paint_val}\n"
        tg_report_1_text += f" • ⏱️ T60: {t60_val}\n"
        tg_report_1_text += f" • ✅ Ready for TCF: {t1_ready}\n"
        tg_report_1_text += f" • 🚫 Shortages: {t1_blocked_summary}\n\n"
        tg_report_1_text += f"🏭 TCF2 LINE (Harrier / Safari):\n"
        tg_report_1_text += f" • 🚜 Dropping: {tcf2_drop_val}\n"
        tg_report_1_text += f" • 🎨 Paint Lifting: {tcf2_paint_val}\n"
        tg_report_1_text += f" • ⏱️ T40: {t40_val}\n"
        tg_report_1_text += f" • ✅ Ready for TCF: {t2_ready}\n"
        tg_report_1_text += f" • 🚫 Shortages: {t2_blocked_summary}\n\n"
        tg_report_1_text += f"📦 PBS Cab details:\n\n"
        tg_report_1_text += f" • 🚜 TCF1: {t1_pbs_total} ({t1_qa_hold} QA hold, {t1_shortages_cnt} Material Shortage)\n"
        tg_report_1_text += f" • 🚜 TCF2: {t2_pbs_total} ({t2_qa_hold} QA hold, {t2_shortages_cnt} Material Shortage)\n\n"
        tg_report_1_text += f"⚡ Punch EV (Nova) VIN Qty: {nova_vin_qty}\n"
        tg_report_1_text += f"⏲️ Current Material clearance after 06:30 AM:\n"

        if 'nova_materials_df' in st.session_state and st.session_state.nova_materials_df is not None:
            for idx, r_n in st.session_state.nova_materials_df.iterrows():
                m_name = str(r_n['Material']).strip()
                m_name_clean = m_name.replace('Craddle', 'Cradle')
                if 'Tube Frame' in m_name_clean and 'Tube Frame (' not in m_name_clean:
                    m_name_clean = m_name_clean.replace('Tube Frame(', 'Tube Frame (')
                if 'new_nova_input_vals' in locals() and m_name in new_nova_input_vals:
                    open_qty = int(new_nova_input_vals[m_name])
                else:
                    open_qty = int(r_n['Clearance Qty'])
                
                if open_qty < nova_vin_qty:
                    defic = nova_vin_qty - open_qty
                    icon = "🔴"
                    tg_report_1_text += f" • {icon} SHORTAGE: {m_name_clean}: {open_qty} (VIN Demand: {nova_vin_qty}, Deficit: -{defic})\n"
                elif open_qty == 0:
                    icon = "🔴"
                    tg_report_1_text += f" • {icon} {m_name_clean}: {open_qty}\n"
                else:
                    icon = "🟢"
                    tg_report_1_text += f" • {icon} {m_name_clean}: {open_qty}\n"

        if 'model_shortages_df' in st.session_state and st.session_state.model_shortages_df is not None and not st.session_state.model_shortages_df.empty:
            tg_report_1_text += f"\n📦 Model-Wise Material Shortage Alerts:\n"
            for idx_ms, r_ms in st.session_state.model_shortages_df.iterrows():
                ms_mod = str(r_ms['Model']).strip()
                ms_trm = str(r_ms.get('Trims', 'All Trims')).strip()
                ms_part = str(r_ms['Part Name']).strip()
                ms_c_qty = int(r_ms['Clearance Qty'])
                ms_d_qty = get_demand_qty_for_model_trims(ms_mod, ms_trm, tcf1_drops, tcf2_drops)
                if ms_c_qty < ms_d_qty:
                    ms_def = ms_d_qty - ms_c_qty
                    tg_report_1_text += f" • 🔴 SHORTAGE: {ms_mod} [{ms_trm}] - {ms_part}: {ms_c_qty} (Demand: {ms_d_qty}, Deficit: -{ms_def})\n"
                else:
                    tg_report_1_text += f" • 🟢 {ms_mod} [{ms_trm}] - {ms_part}: {ms_c_qty} (Demand: {ms_d_qty})\n"

        # ----------------- REPORT 2: PUNCH EV (NOVA) EXECUTIVE STATUS REPORT -----------------
        now_time_r2 = format_ist_nearest_15min().replace(" ", "")  # e.g. "04.15PM"
        nova_paint_float_cnt = 0
        nova_pbs_cnt = 0

        if 'paint_summary_dict' in locals() and paint_summary_dict and 'PUNCH.EV' in paint_summary_dict:
            m_nova = paint_summary_dict['PUNCH.EV']
            nova_paint_float_cnt = m_nova.get('TOTAL FLOAT', 0)
            nova_pbs_cnt = m_nova.get('PBS FLOAT', 0)
        elif float_df is not None and not float_df.empty:
            is_nova_mask = (
                float_df['PRODUCT'].astype(str).str.upper().str.contains('NOVA') |
                float_df['VEHICLE CODE'].astype(str).str.startswith('5468')
            )
            nova_float_cabs = float_df[is_nova_mask]
            nova_paint_float_cnt = len(nova_float_cabs)
            nova_pbs_cnt = len(nova_float_cabs[nova_float_cabs['PBS LIFT'].notna()])

        tg_report_2_text = f"Dear sir,\n\n"
        tg_report_2_text += f"Nova Status as on {now_time_r2}\n\n"
        tg_report_2_text += f"VIN: {nova_vin_qty}\n\n"
        tg_report_2_text += f"Current Paint Float: {nova_paint_float_cnt}\n"
        tg_report_2_text += f"PBS: {nova_pbs_cnt}\n\n"
        tg_report_2_text += f"Today's Material Clearance (after 06:30 AM):\n\n"

        if 'nova_materials_df' in st.session_state and st.session_state.nova_materials_df is not None:
            for idx, r_n in st.session_state.nova_materials_df.iterrows():
                m_name = str(r_n['Material']).strip()
                m_name_clean = m_name.replace('Craddle', 'Cradle')
                if 'Tube Frame' in m_name_clean and 'Tube Frame (' not in m_name_clean:
                    m_name_clean = m_name_clean.replace('Tube Frame(', 'Tube Frame (')
                if 'new_nova_input_vals' in locals() and m_name in new_nova_input_vals:
                    open_qty = int(new_nova_input_vals[m_name])
                else:
                    open_qty = int(r_n['Clearance Qty'])
                
                # Add * to lower stock qty only (stock < VIN Qty)
                if open_qty < nova_vin_qty:
                    defic = nova_vin_qty - open_qty
                    tg_report_2_text += f"🚨 *SHORTAGE: {m_name_clean}: {open_qty} (Demand: {nova_vin_qty}, Deficit: -{defic})*\n"
                else:
                    tg_report_2_text += f"{m_name_clean}: {open_qty}\n"

        if 'model_shortages_df' in st.session_state and st.session_state.model_shortages_df is not None and not st.session_state.model_shortages_df.empty:
            tg_report_2_text += f"\nModel Shortages:\n"
            for idx_ms, r_ms in st.session_state.model_shortages_df.iterrows():
                ms_mod = str(r_ms['Model']).strip()
                ms_trm = str(r_ms.get('Trims', 'All Trims')).strip()
                ms_part = str(r_ms['Part Name']).strip()
                ms_c_qty = int(r_ms['Clearance Qty'])
                ms_d_qty = get_demand_qty_for_model_trims(ms_mod, ms_trm, tcf1_drops, tcf2_drops)
                if ms_c_qty < ms_d_qty:
                    ms_def = ms_d_qty - ms_c_qty
                    tg_report_2_text += f"🚨 *SHORTAGE: {ms_mod} [{ms_trm}] - {ms_part}: {ms_c_qty} (Demand: {ms_d_qty}, Deficit: -{ms_def})*\n"
                else:
                    tg_report_2_text += f"{ms_mod} [{ms_trm}] - {ms_part}: {ms_c_qty}\n"
        # Build Report 3: TCF Dropping vs. Paint Lifting Status
        tcf1_gap_str = f"\n*Gap:{tcf1_drop_val - tcf1_paint_val:02d}*" if tcf1_drop_val >= tcf1_paint_val else ""
        tcf2_gap_str = f"\n *Gap: {tcf2_drop_val - tcf2_paint_val:02d}* " if tcf2_drop_val >= tcf2_paint_val else ""
        
        tcf1_pbs_detail_str = f"{t1_ready} cabs ({t1_qa_hold} QA hold, {t1_shortages_cnt} Material Shortage)"
        tcf2_pbs_detail_str = f"{t2_ready} cabs ({t2_qa_hold} QA hold, {t2_shortages_cnt} Material Shortage)"

        tg_report_3_text = f"""Dear Sir

TCF Dropping vs. Paint Lifting Status:

TCF1:
Dropping: {tcf1_drop_val}
Paint Lifting: {tcf1_paint_val}{tcf1_gap_str}

TCF2:
Dropping : {tcf2_drop_val}
Paint Lifting: {tcf2_paint_val}{tcf2_gap_str}

Dropping Float:
*T60: {t60_val}*
*T40: {t40_val}*

Available Cabs for VIN Generation:

TCF1: {tcf1_pbs_detail_str}

TCF2: {tcf2_pbs_detail_str}"""

        # ----------------- AUTO-SEND 3 REPORTS (15-MIN INTERVAL) -----------------
        with st.container(border=True):
            as_col1, as_col2 = st.columns([3, 1.4])
            with as_col1:
                st.markdown("##### ⏰ Auto-Send 3 Reports (15-Minute Intervals)")
                st.caption(
                    "Automatically dispatches all 3 reports to Telegram at exact 15-minute clock intervals "
                    "(e.g., **6:00 PM**, **6:15 PM**, **6:30 PM**, **6:45 PM**). Reports are **not** sent in-between."
                )
            with as_col2:
                cur_auto_state = st.session_state.get('telegram_auto_send_15m', False)
                tg_auto_toggle = st.toggle(
                    "⏱️ **Auto-Send ON / OFF**",
                    value=cur_auto_state,
                    key="tg_auto_send_toggle"
                )
                if tg_auto_toggle != cur_auto_state:
                    st.session_state.telegram_auto_send_15m = tg_auto_toggle
                    try:
                        dl.save_metadata('telegram_auto_send_15m', str(tg_auto_toggle))
                    except Exception:
                        pass
                    if tg_auto_toggle:
                        st.toast("⏰ 15-Minute Auto-Send Enabled! Reports will dispatch at :00, :15, :30, :45.", icon="⏰")
                    else:
                        st.toast("⏹️ 15-Minute Auto-Send Disabled.", icon="⏹️")
                    st.rerun()

            # Status information metrics
            now_dt = get_ist_now()
            last_sent_time = dl.load_metadata('last_auto_tg_sent_time', 'None yet')
            last_sent_status = dl.load_metadata('last_auto_tg_status', 'Idle')
            cur_slot = now_dt.strftime("%Y-%m-%d %H:%M")
            last_sent_slot = dl.load_metadata('last_auto_tg_sent_slot', '')
            
            cur_min = now_dt.minute
            rem_min = cur_min % 15
            
            if rem_min == 0 and last_sent_slot != cur_slot:
                next_slot_str = now_dt.strftime("%I:%M %p (Dispatching now...)")
            else:
                add_mins = 15 - rem_min if rem_min != 0 else 15
                next_trigger = (now_dt + timedelta(minutes=add_mins)).replace(second=0, microsecond=0)
                next_slot_str = next_trigger.strftime("%I:%M %p")

            m_c1, m_c2, m_c3, m_c4 = st.columns(4)
            with m_c1:
                if cur_auto_state:
                    st.markdown("🟢 **Status:** <span style='color:#10B981;font-weight:600;'>Active (:00, :15, :30, :45)</span>", unsafe_allow_html=True)
                else:
                    st.markdown("⚪ **Status:** <span style='color:#6B7280;font-weight:600;'>Disabled (OFF)</span>", unsafe_allow_html=True)
            with m_c2:
                st.markdown(f"🕐 **Current IST:** `{now_dt.strftime('%I:%M %p')}`")
            with m_c3:
                st.markdown(f"⏳ **Next Trigger:** `{next_slot_str}`")
            with m_c4:
                st.markdown(f"📡 **Last Sent:** `{last_sent_time}`")

            if cur_auto_state and last_sent_status and last_sent_status != 'Idle':
                st.caption(f"ℹ️ {last_sent_status}")

        # Auto-send execution check on 15-min mark (:00, :15, :30, :45)
        if st.session_state.get('telegram_auto_send_15m', False):
            now_ist = get_ist_now()
            # Strictly check if current minute is exactly 0, 15, 30, or 45
            if now_ist.minute in (0, 15, 30, 45):
                slot_key = now_ist.strftime("%Y-%m-%d %H:%M")
                last_slot_db = dl.load_metadata('last_auto_tg_sent_slot', '')
                
                if last_slot_db != slot_key:
                    # Save slot immediately to prevent duplicate dispatches
                    dl.save_metadata('last_auto_tg_sent_slot', slot_key)
                    st.session_state.last_auto_tg_sent_slot = slot_key
                    
                    bot_tok = st.session_state.get('telegram_token', '').strip()
                    chat_id_val = st.session_state.get('telegram_chat_id', '').strip()
                    
                    if bot_tok and chat_id_val:
                        ok1, res1 = dl.send_telegram_message(bot_tok, chat_id_val, tg_report_1_text)
                        ok2, res2 = dl.send_telegram_message(bot_tok, chat_id_val, tg_report_2_text)
                        ok3, res3 = dl.send_telegram_message(bot_tok, chat_id_val, tg_report_3_text)
                        
                        ts_str = format_ist_now("%d-%m-%Y %I:%M %p")
                        if ok1 and ok2 and ok3:
                            msg_stat = f"✅ All 3 reports auto-dispatched successfully at {now_ist.strftime('%I:%M %p')}"
                            dl.save_metadata('last_auto_tg_sent_time', ts_str)
                            dl.save_metadata('last_auto_tg_status', msg_stat)
                            st.session_state.last_auto_tg_sent_time = ts_str
                            st.session_state.last_auto_tg_status = msg_stat
                            st.toast(f"🚀 Auto-dispatched 3 reports for {now_ist.strftime('%I:%M %p')} to Telegram!", icon="🚀")
                        else:
                            err_list = []
                            if not ok1: err_list.append(f"Report 1: {res1}")
                            if not ok2: err_list.append(f"Report 2: {res2}")
                            if not ok3: err_list.append(f"Report 3: {res3}")
                            msg_stat = f"⚠️ Dispatched with errors at {now_ist.strftime('%I:%M %p')}: {', '.join(err_list)}"
                            dl.save_metadata('last_auto_tg_sent_time', ts_str)
                            dl.save_metadata('last_auto_tg_status', msg_stat)
                            st.session_state.last_auto_tg_sent_time = ts_str
                            st.session_state.last_auto_tg_status = msg_stat
                            st.toast(f"⚠️ Auto-send error at {now_ist.strftime('%I:%M %p')}", icon="⚠️")

        # ----------------- QUICK ACTIONS: SEND ALL 3 SCHEDULED REPORTS -----------------
        with st.container(border=True):
            qa_col1, qa_col2 = st.columns([3, 1.4])
            with qa_col1:
                st.markdown("##### ⚡ Quick Action")
                st.caption("Send the TCF1 & TCF2 PPC Report, the Nova Status Report, and the Dropping vs. Paint Lifting Status Report together in one tap.")
            with qa_col2:
                if st.button("🚀 Send ALL 3 Reports Now", type="secondary", use_container_width=True, key="send_all_tg_reports_btn"):
                    ok1, res_msg1 = dl.send_telegram_message(st.session_state.telegram_token, st.session_state.telegram_chat_id, tg_report_1_text)
                    ok2, res_msg2 = dl.send_telegram_message(st.session_state.telegram_token, st.session_state.telegram_chat_id, tg_report_2_text)
                    ok3, res_msg3 = dl.send_telegram_message(st.session_state.telegram_token, st.session_state.telegram_chat_id, tg_report_3_text)
                    if ok1 and ok2 and ok3:
                        st.toast("🚀 All 3 reports successfully sent to Telegram!", icon="🚀")
                        st.success("✅ All 3 reports (TCF1 & TCF2 PPC Report, Nova Status Report, and Dropping vs. Paint Lifting Status) dispatched successfully!")
                    else:
                        if not ok1:
                            st.error(f"Report 1 Error: {res_msg1}")
                        if not ok2:
                            st.error(f"Report 2 Error: {res_msg2}")
                        if not ok3:
                            st.error(f"Report 3 Error: {res_msg3}")

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
        st.caption("📅 **Scheduled Report Templates** (first 3 tabs) — preview and send one at a time · 💬 **Manual Dispatcher** (last tab) — free-text, screenshots, or file attachments")

        # Tabbed preview & dispatch options
        report_tab1, report_tab2, report_tab3, report_tab4 = st.tabs([
            "📅 Report 1: TCF1 & TCF2 PPC Report",
            "📅 Report 2: Punch EV (Nova) Status Report",
            "📅 Report 3: TCF Dropping vs. Paint Lifting Status",
            "💬 Custom Telegram Dispatcher"
        ])

        with report_tab1:
            st.markdown("##### 📊 TCF1 & TCF2 PPC Report Preview")
            st.markdown(f"<div style='background: rgba(15, 23, 42, 0.05); border-radius: 8px; padding: 14px; font-family: monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all;'>{tg_report_1_text}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("🚀 Send TCF1 & TCF2 Report to Telegram", type="primary", use_container_width=True, key="send_tg_report_1_btn"):
                ok, res_msg = dl.send_telegram_message(st.session_state.telegram_token, st.session_state.telegram_chat_id, tg_report_1_text)
                if ok:
                    st.toast("🚀 TCF1 & TCF2 Report successfully sent to Telegram!", icon="🚀")
                    st.success("✅ TCF1 & TCF2 Report dispatched successfully!")
                else:
                    st.error(res_msg)

        with report_tab2:
            st.markdown("##### ⚡ Punch EV (Nova) Status Report Preview")
            st.markdown(f"<div style='background: rgba(15, 23, 42, 0.05); border-radius: 8px; padding: 14px; font-family: monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all;'>{tg_report_2_text}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("🚀 Send Nova Status Report to Telegram", type="primary", use_container_width=True, key="send_tg_report_2_btn"):
                ok, res_msg = dl.send_telegram_message(st.session_state.telegram_token, st.session_state.telegram_chat_id, tg_report_2_text)
                if ok:
                    st.toast("🚀 Nova Status Report successfully sent to Telegram!", icon="🚀")
                    st.success("✅ Nova Status Report dispatched successfully!")
                else:
                    st.error(res_msg)

        with report_tab3:
            st.markdown("##### 🏭 TCF Dropping vs. Paint Lifting Status Report Preview")
            st.markdown(f"<div style='background: rgba(15, 23, 42, 0.05); border-radius: 8px; padding: 14px; font-family: monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all;'>{tg_report_3_text}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("🚀 Send Dropping vs. Paint Lifting Report to Telegram", type="primary", use_container_width=True, key="send_tg_report_3_btn"):
                ok, res_msg = dl.send_telegram_message(st.session_state.telegram_token, st.session_state.telegram_chat_id, tg_report_3_text)
                if ok:
                    st.toast("🚀 Dropping vs. Paint Lifting Report successfully sent to Telegram!", icon="🚀")
                    st.success("✅ Dropping vs. Paint Lifting Report dispatched successfully!")
                else:
                    st.error(res_msg)

        with report_tab4:
            st.markdown("##### 💬 Custom / Manual Telegram Dispatcher")
            st.markdown("<small style='color:#8896AB'>Paste any custom text message, paste screenshots directly from clipboard, or attach Excel / document files to send to your mobile via Telegram Bot.</small>", unsafe_allow_html=True)
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

            custom_text = st.text_area("✍️ Custom Text Message (Optional if uploading file/image):", height=130, placeholder="Type or paste text message here...", key="custom_tg_text_input")
            
            c_col1, c_col2 = st.columns(2)
            img_bytes_to_send = None
            img_filename_to_send = "screenshot.png"

            with c_col1:
                st.markdown("##### 🖼️ Image / Screenshot Attachment")
                st.markdown("<small style='color:#8896AB'>Capture with Snipping Tool (Win + Shift + S), then click below:</small>", unsafe_allow_html=True)
                
                pasted_img_res = paste_image_button(
                    label="📋 Paste Screenshot from Clipboard",
                    background_color="#2563EB",
                    text_color="#FFFFFF",
                    hover_background_color="#1D4ED8",
                    key="custom_tg_paste_btn"
                )
                
                custom_img = st.file_uploader("Or Upload Image File", type=["png", "jpg", "jpeg", "webp"], key="custom_tg_img_uploader")

                if pasted_img_res and pasted_img_res.image_data is not None:
                    st.success("✅ Screenshot captured from Clipboard!")
                    st.image(pasted_img_res.image_data, caption="Clipboard Screenshot Preview", use_column_width=True)
                    img_buf = io.BytesIO()
                    pasted_img_res.image_data.save(img_buf, format="PNG")
                    img_bytes_to_send = img_buf.getvalue()
                elif custom_img is not None:
                    img_bytes_to_send = custom_img.getvalue()
                    img_filename_to_send = custom_img.name

            with c_col2:
                st.markdown("##### 📁 Excel / Document / Image File Attachment (Option 2)")
                st.markdown("<small style='color:#8896AB'>Upload ANY files (Excel, PDF, Images PNG/JPG, Word, CSV, ZIP, etc.):</small>", unsafe_allow_html=True)
                custom_docs = st.file_uploader("Upload Files (Excel, PDF, Images, Documents, etc.)", accept_multiple_files=True, key="custom_tg_doc_uploader")

            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button("🚀 Send Custom Message / Files via Telegram Bot", type="primary", use_container_width=True, key="send_custom_tg_msg_btn"):
                has_text = bool(custom_text and custom_text.strip())
                has_img = img_bytes_to_send is not None
                has_docs = bool(custom_docs)

                if not has_text and not has_img and not has_docs:
                    st.warning("⚠️ Please enter a text message, paste a screenshot, or select file(s) to send.")
                else:
                    bot_token = st.session_state.get('telegram_token', '')
                    chat_id = st.session_state.get('telegram_chat_id', '')

                    successes = []
                    errors = []
                    caption_used = False

                    # 1. Send Text if provided (and no file attachments)
                    if has_text and not has_img and not has_docs:
                        ok, msg = dl.send_telegram_message(bot_token, chat_id, custom_text.strip())
                        if ok:
                            successes.append("Custom text message sent successfully!")
                        else:
                            errors.append(f"Text Message Error: {msg}")

                    # 2. Send Col 1 / Clipboard Image if provided
                    if has_img:
                        caption_str = custom_text.strip() if (has_text and not caption_used) else ""
                        ok, msg = dl.send_telegram_photo(bot_token, chat_id, img_bytes_to_send, caption=caption_str, filename=img_filename_to_send)
                        if ok:
                            successes.append(f"Image ({img_filename_to_send}) sent successfully!")
                            caption_used = True
                        else:
                            errors.append(f"Image Error: {msg}")

                    # 3. Send Files from Col 2 (Images, Excel, PDF, Word, etc.)
                    if has_docs:
                        for doc_file in custom_docs:
                            f_bytes = doc_file.getvalue()
                            f_name = doc_file.name
                            caption_str = custom_text.strip() if (has_text and not caption_used) else ""
                            
                            # Auto-detect if file is an image format
                            ext = os.path.splitext(f_name)[1].lower()
                            if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']:
                                ok, msg = dl.send_telegram_photo(bot_token, chat_id, f_bytes, caption=caption_str, filename=f_name)
                                if ok:
                                    successes.append(f"Image ({f_name}) sent successfully!")
                                    caption_used = True
                                else:
                                    errors.append(f"File Error ({f_name}): {msg}")
                            else:
                                ok, msg = dl.send_telegram_document(bot_token, chat_id, f_bytes, caption=caption_str, filename=f_name)
                                if ok:
                                    successes.append(f"File ({f_name}) sent successfully!")
                                    caption_used = True
                                else:
                                    errors.append(f"File Error ({f_name}): {msg}")

                    if successes:
                        for s_msg in successes:
                            st.toast(f"🚀 {s_msg}", icon="🚀")
                            st.success(f"✅ {s_msg}")
                    if errors:
                        for e_msg in errors:
                            st.error(f"❌ {e_msg}")

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
