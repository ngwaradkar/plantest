import os
import sys
import logging
import traceback
import io
import streamlit as st
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

import data_loader as dl
import allocation_engine as ae
from core import cache_manager

# Project paths
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default engine configuration
ENGINE_DEFAULT_DATA = [
    {"Model": "Punch (Hornbill)", "Engine Part No": "544201100147", "TCF Line": "TCF1", "Clearance After 6:30AM": 0},
    {"Model": "Punch (Hornbill)", "Engine Part No": "544201100148", "TCF Line": "TCF1", "Clearance After 6:30AM": 0},
    {"Model": "Punch (Hornbill)", "Engine Part No": "544201100161", "TCF Line": "TCF1", "Clearance After 6:30AM": 0},
    {"Model": "Punch (Hornbill)", "Engine Part No": "544201100162", "TCF Line": "TCF1", "Clearance After 6:30AM": 0},
    {"Model": "Punch (Hornbill)", "Engine Part No": "544201100163", "TCF Line": "TCF1", "Clearance After 6:30AM": 0},
    {"Model": "Punch (Hornbill)", "Engine Part No": "544201100171", "TCF Line": "TCF1", "Clearance After 6:30AM": 0},
    {"Model": "Punch (Hornbill)", "Engine Part No": "544201100172", "TCF Line": "TCF1", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100147", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100148", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100149", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100150", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100151", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100152", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100153", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100154", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100155", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100156", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100157", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
    {"Model": "Harrier / Safari", "Engine Part No": "542701100158", "TCF Line": "TCF2", "Clearance After 6:30AM": 0},
]

@dataclass
class DashboardData:
    """Holds all computed results for the dashboard and all pages."""
    bom_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    float_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    vgl_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    alloc_results: List[Dict[str, Any]] = field(default_factory=list)
    paint_summary: Dict[str, Any] = field(default_factory=dict)
    paint_summary_vc_dict: Dict[str, Any] = field(default_factory=dict)
    
    tcf1_drops: Optional[pd.DataFrame] = None
    tcf2_drops: Optional[pd.DataFrame] = None
    
    hourly_df: Optional[pd.DataFrame] = None
    shop_totals: Optional[Dict[str, Any]] = None
    shop_vehicles_df: Optional[pd.DataFrame] = None
    shop_ta_df: Optional[pd.DataFrame] = None
    
    true_engine_tcf1: Dict[str, Any] = field(default_factory=dict)
    true_cockpit_tcf1: Dict[str, Any] = field(default_factory=dict)
    true_wiring_tcf1: Dict[str, Any] = field(default_factory=dict)
    
    true_engine_tcf2: Dict[str, Any] = field(default_factory=dict)
    true_cockpit_tcf2: Dict[str, Any] = field(default_factory=dict)
    true_wiring_tcf2: Dict[str, Any] = field(default_factory=dict)
    
    tcf1_alloc_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    tcf2_alloc_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    tcf1_final_stocks: Dict[str, Any] = field(default_factory=dict)
    tcf2_final_stocks: Dict[str, Any] = field(default_factory=dict)
    
    tcf1_total_alloc_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    tcf2_total_alloc_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    shortage_report: pd.DataFrame = field(default_factory=pd.DataFrame)
    missing_bom_vcs: pd.DataFrame = field(default_factory=pd.DataFrame)
    
    status: str = "success"
    error_message: str = ""


def get_backflushed_vin_count_for_model_trims(target_model, target_trims_str, tcf1_drops, tcf2_drops):
    """Helper to count drops today matching a target model and trim string."""
    drops_list = []
    if tcf1_drops is not None and not tcf1_drops.empty:
        drops_list.append(tcf1_drops)
    if tcf2_drops is not None and not tcf2_drops.empty:
        drops_list.append(tcf2_drops)
    if not drops_list:
        return 0
    all_drops = pd.concat(drops_list, ignore_index=True)
    if 'PRODUCT' not in all_drops.columns:
        return 0
    
    trims_list = [t.strip() for t in target_trims_str.split(',') if t.strip()] if target_trims_str and target_trims_str != 'All Trims' else []
    match_count = 0
    for _, row in all_drops.iterrows():
        prod = str(row.get('PRODUCT', ''))
        s_desc = str(row.get('SALES DESCRIPTION', ''))
        if ae._is_model_trim_matched(prod, s_desc, target_model, trims_list):
            match_count += int(row.get('VIN_Count', 1)) if pd.notna(row.get('VIN_Count')) and str(row.get('VIN_Count')).isdigit() else 1
    return match_count


def get_dashboard_data(classified_files: Optional[Dict[str, Any]] = None) -> DashboardData:
    """
    Complete data pipeline:
    1. Checks signature of input files + engine/nova state.
    2. Returns cached DashboardData if unchanged.
    3. Loads all files (BOM, Float, Paint, VGL, Stocks).
    4. Computes True Stocks with Backflushing.
    5. Runs PBS & Total Float FIFO allocations.
    6. Maps Trims & Models.
    7. Computes Stagewise Shortage & Missing BOMs.
    8. Caches and returns DashboardData.
    """
    if classified_files is None or not classified_files:
        data_source = st.session_state.get('data_source_dir', 'Root Directory (Production)')
        active_dir = os.path.join(WORKSPACE_DIR, "TEST") if data_source == 'TEST Directory (Sample Data)' else WORKSPACE_DIR
        classified_files = dl.detect_and_classify_files(active_dir)
        st.session_state['classified_files'] = classified_files

    # 1. Compute signature of all input files to detect changes
    combined_sig_input = ""
    for k in sorted(classified_files.keys()):
        file_obj = classified_files[k]
        combined_sig_input += f"{k}:{cache_manager.compute_file_signature(file_obj)}_"
        
    # Also incorporate stock edits signature
    engine_sig = str(st.session_state.get('engine_df', ''))
    nova_sig = str(st.session_state.get('nova_materials_df', ''))
    model_sig = str(st.session_state.get('model_shortages_df', ''))
    combined_sig_input += f"eng:{engine_sig}_nova:{nova_sig}_ms:{model_sig}"
    
    current_signature = cache_manager.compute_file_signature(combined_sig_input)
    
    # 2. Return cached data if signature matches
    if st.session_state.get('dashboard_signature') == current_signature:
        if st.session_state.get('dashboard_data') is not None:
            return st.session_state['dashboard_data']

    # 3. Load all data and run calculations
    try:
        # Load BOM
        bom_df = None
        if 'BOM' in classified_files:
            bom_df = dl.load_bom(classified_files['BOM'])
            try:
                dl.save_bom_to_db(bom_df)
            except Exception:
                pass
        if bom_df is None or bom_df.empty:
            bom_df = dl.load_bom_from_db()
            
        # Build BOM fast lookup dictionary for O(1) matching
        bom_lookup = {}
        if bom_df is not None and not bom_df.empty and 'Short Vehicle Code' in bom_df.columns:
            for r in bom_df.to_dict('records'):
                svc = str(r.get('Short Vehicle Code', '')).strip()
                if svc:
                    bom_lookup[svc] = r
                    
        # Load Float Reports
        float_df = dl.load_float_report(classified_files['FLOAT_REPORT']) if 'FLOAT_REPORT' in classified_files else None
        paint_summary = dl.load_paint_summary_report(classified_files['FLOAT_PAINT_SUMMARY']) if 'FLOAT_PAINT_SUMMARY' in classified_files else {}
        paint_summary_vc = dl.load_paint_summary_by_vc(classified_files['FLOAT_PAINT_SUMMARY']) if 'FLOAT_PAINT_SUMMARY' in classified_files else {}
        
        # Load VGL drops
        tcf1_drops = dl.load_vgl(classified_files['TCF1_VGL']) if 'TCF1_VGL' in classified_files else None
        tcf2_drops = dl.load_vgl(classified_files['TCF2_VGL']) if 'TCF2_VGL' in classified_files else None
        
        # Load Hourly Production & Shop-Wise
        hourly_df = dl.load_hourly_production(classified_files['HOURLY_PRODUCTION']) if 'HOURLY_PRODUCTION' in classified_files else None
        shop_totals, shop_vehicles_df, shop_ta_df = None, None, None
        if 'SHOP_WISE_REPORT' in classified_files:
            try:
                shop_totals, shop_vehicles_df, shop_ta_df = dl.load_shop_wise_report(classified_files['SHOP_WISE_REPORT'])
            except Exception:
                pass
                
        # Load Wiring Stock
        tcf1_wiring_start = {}
        if 'TCF1_WIRING_STOCK' in classified_files:
            s_map, _ = dl.load_stock_grouped(
                classified_files['TCF1_WIRING_STOCK'],
                sheet_name='Coverage file 6.30 AM New',
                vc_col_idx=2, part_col_idx=3, qty_col_idx=9
            )
            tcf1_wiring_start = s_map or {}
            
        tcf2_wiring_start = {}
        if 'TCF2_WIRING_STOCK' in classified_files:
            s_map, _ = dl.load_stock_grouped(
                classified_files['TCF2_WIRING_STOCK'],
                sheet_name='coverage file 6.30 pm',
                vc_col_idx=1, part_col_idx=2, qty_col_idx=9
            )
            tcf2_wiring_start = s_map or {}
            
        # Load Cockpit Stock
        tcf1_cockpit_start = {}
        if 'TCF1_ALTROZ_COCKPIT_STOCK' in classified_files:
            alt_s, _ = dl.load_stock_grouped(
                classified_files['TCF1_ALTROZ_COCKPIT_STOCK'],
                sheet_name='Fresh VIN PPC',
                vc_col_idx=4, part_col_idx=3, qty_col_idx=12, skip_rows=3
            )
            tcf1_cockpit_start.update(alt_s or {})
            
        if 'TCF1_NOVA_COCKPIT_STOCK' in classified_files:
            nov_s, _ = dl.load_stock_grouped(
                classified_files['TCF1_NOVA_COCKPIT_STOCK'],
                sheet_name='Fresh VIN PPC',
                vc_col_idx=1, part_col_idx=0, qty_col_idx=9, skip_rows=3
            )
            tcf1_cockpit_start.update(nov_s or {})
            
        tcf2_cockpit_start = {}
        if 'TCF2_COCKPIT_STOCK' in classified_files:
            t2_ck, _ = dl.load_stock_grouped(
                classified_files['TCF2_COCKPIT_STOCK'],
                sheet_name='Fresh vin PPC',
                vc_col_idx=3, part_col_idx=1, qty_col_idx=9, skip_rows=3
            )
            tcf2_cockpit_start = t2_ck or {}
            
        # Load Engine Starting Stock
        if 'engine_df' not in st.session_state or st.session_state.engine_df is None or st.session_state.engine_df.empty:
            db_eng = dl.load_engine_stocks_from_db()
            st.session_state.engine_df = db_eng if db_eng is not None and not db_eng.empty else pd.DataFrame(ENGINE_DEFAULT_DATA)
            
        engine_stocks_tcf1 = {}
        engine_stocks_tcf2 = {}
        for _, row in st.session_state.engine_df.iterrows():
            part = str(row['Engine Part No']).strip()
            qty = int(row['Clearance After 6:30AM'])
            if row.get('TCF Line') == 'TCF1':
                engine_stocks_tcf1[part] = qty
            else:
                engine_stocks_tcf2[part] = qty
                
        # Punch EV Nova Clearance
        if 'nova_materials_df' not in st.session_state or st.session_state.nova_materials_df is None:
            st.session_state.nova_materials_df = dl.load_nova_stocks_from_db()
            
        if st.session_state.nova_materials_df is not None and not st.session_state.nova_materials_df.empty:
            engine_stocks_tcf1['546816111212'] = int(st.session_state.nova_materials_df['Clearance Qty'].min())
        else:
            engine_stocks_tcf1['546816111212'] = 182
            
        # Harrier EV Clearance
        engine_stocks_tcf2['547380400103'] = 160
        
        # 4. BACKFLUSH LOGIC (calculate true stocks)
        true_engine_tcf1, eng_cons_tcf1, _ = ae.calculate_true_stock(engine_stocks_tcf1, tcf1_drops, bom_df, 'Engine', bom_lookup=bom_lookup)
        true_cockpit_tcf1, ck_cons_tcf1, _ = ae.calculate_true_stock(tcf1_cockpit_start, tcf1_drops, bom_df, 'Cockpit', bom_lookup=bom_lookup)
        true_wiring_tcf1, wh_cons_tcf1, _ = ae.calculate_true_stock(tcf1_wiring_start, tcf1_drops, bom_df, 'Front Wiring', bom_lookup=bom_lookup)
        
        true_engine_tcf2, eng_cons_tcf2, _ = ae.calculate_true_stock(engine_stocks_tcf2, tcf2_drops, bom_df, 'Engine', bom_lookup=bom_lookup)
        true_cockpit_tcf2, ck_cons_tcf2, _ = ae.calculate_true_stock(tcf2_cockpit_start, tcf2_drops, bom_df, 'Cockpit', bom_lookup=bom_lookup)
        true_wiring_tcf2, wh_cons_tcf2, _ = ae.calculate_true_stock(tcf2_wiring_start, tcf2_drops, bom_df, 'Front Wiring', bom_lookup=bom_lookup)
        
        # Punch EV Nova true material stock dict
        true_nova_dict = {}
        nova_backflushed = eng_cons_tcf1.get('546816111212', 0)
        if st.session_state.nova_materials_df is not None and not st.session_state.nova_materials_df.empty:
            for _, r_nova in st.session_state.nova_materials_df.iterrows():
                mat_name = str(r_nova['Material']).strip()
                start_qty = int(r_nova['Clearance Qty'])
                true_nova_dict[mat_name] = start_qty - nova_backflushed
                
        # Model-Wise Shortage stock list
        if 'model_shortages_df' not in st.session_state or st.session_state.model_shortages_df is None:
            st.session_state.model_shortages_df = dl.load_model_shortages_from_db()
            
        model_shortages_list = []
        if st.session_state.model_shortages_df is not None and not st.session_state.model_shortages_df.empty:
            for _, r_ms in st.session_state.model_shortages_df.iterrows():
                m_mod = str(r_ms['Model']).strip()
                m_trm = str(r_ms.get('Trims', 'All Trims')).strip()
                m_part = str(r_ms['Part Name']).strip()
                start_qty = int(r_ms['Clearance Qty'])
                vins_today = get_backflushed_vin_count_for_model_trims(m_mod, m_trm, tcf1_drops, tcf2_drops)
                true_stock = max(0, start_qty - vins_today)
                model_shortages_list.append({
                    'Model': m_mod,
                    'Trims': m_trm,
                    'Part Name': m_part,
                    'Stock': true_stock,
                    'Clearance Qty': start_qty,
                    'Backflushed VINs': vins_today
                })

        # 5. PBS QUEUE ALLOCATION (TCF1 & TCF2 Line Tabs)
        tcf1_alloc_df = pd.DataFrame()
        tcf2_alloc_df = pd.DataFrame()
        tcf1_final_stocks = {}
        tcf2_final_stocks = {}
        tcf1_total_alloc_df = pd.DataFrame()
        tcf2_total_alloc_df = pd.DataFrame()
        
        if float_df is not None and not float_df.empty:
            pbs_all = float_df[float_df['PBS LIFT'].notna()].copy() if 'PBS LIFT' in float_df.columns else float_df.copy()
            is_hold_pbs = (pbs_all['HOLD BY'].notna() & 
                           (pbs_all['HOLD BY'].astype(str).str.strip() != '') & 
                           (pbs_all['HOLD BY'].astype(str).str.upper() != 'NONE')) if 'HOLD BY' in pbs_all.columns else pd.Series(False, index=pbs_all.index)
            pbs_active = pbs_all[~is_hold_pbs].copy()
            
            tcf1_queue = pbs_active[pbs_active.get('SHOP', '') == 'TCF1'].copy() if 'SHOP' in pbs_active.columns else pd.DataFrame()
            tcf2_queue = pbs_active[pbs_active.get('SHOP', '') == 'TCF2'].copy() if 'SHOP' in pbs_active.columns else pd.DataFrame()
            
            if not tcf1_queue.empty and 'PBS LIFT' in tcf1_queue.columns:
                tcf1_queue.sort_values(by='PBS LIFT', ascending=True, inplace=True)
            if not tcf2_queue.empty and 'PBS LIFT' in tcf2_queue.columns:
                tcf2_queue.sort_values(by='PBS LIFT', ascending=True, inplace=True)
                
            tcf1_alloc, tcf1_final_stocks = ae.run_allocation(
                tcf1_queue, bom_df, true_engine_tcf1, true_cockpit_tcf1, true_wiring_tcf1,
                true_nova=true_nova_dict, model_shortages=model_shortages_list, bom_lookup=bom_lookup
            )
            tcf2_alloc, tcf2_final_stocks = ae.run_allocation(
                tcf2_queue, bom_df, true_engine_tcf2, true_cockpit_tcf2, true_wiring_tcf2,
                model_shortages=model_shortages_list, bom_lookup=bom_lookup
            )
            tcf1_alloc_df = pd.DataFrame(tcf1_alloc)
            tcf2_alloc_df = pd.DataFrame(tcf2_alloc)
            
            # Total Float Allocation
            is_hold_float = (float_df['HOLD BY'].notna() & 
                             (float_df['HOLD BY'].astype(str).str.strip() != '') & 
                             (float_df['HOLD BY'].astype(str).str.upper() != 'NONE')) if 'HOLD BY' in float_df.columns else pd.Series(False, index=float_df.index)
            float_active = float_df[~is_hold_float].copy()
            tcf1_total_queue = float_active[float_active.get('SHOP', '') == 'TCF1'].copy() if 'SHOP' in float_active.columns else pd.DataFrame()
            tcf2_total_queue = float_active[float_active.get('SHOP', '') == 'TCF2'].copy() if 'SHOP' in float_active.columns else pd.DataFrame()
            
            stage_sort_cols = [c for c in ['PBS LIFT', 'TOPCOAT', 'SEALANT', 'PTCED', 'BIW LIFTING'] if c in float_df.columns]
            if stage_sort_cols:
                if not tcf1_total_queue.empty:
                    tcf1_total_queue.sort_values(by=stage_sort_cols, ascending=[True]*len(stage_sort_cols), na_position='last', inplace=True)
                if not tcf2_total_queue.empty:
                    tcf2_total_queue.sort_values(by=stage_sort_cols, ascending=[True]*len(stage_sort_cols), na_position='last', inplace=True)
                    
            tcf1_tot_alloc, _ = ae.run_allocation(
                tcf1_total_queue, bom_df, true_engine_tcf1, true_cockpit_tcf1, true_wiring_tcf1,
                true_nova=true_nova_dict, model_shortages=model_shortages_list, bom_lookup=bom_lookup
            )
            tcf2_tot_alloc, _ = ae.run_allocation(
                tcf2_total_queue, bom_df, true_engine_tcf2, true_cockpit_tcf2, true_wiring_tcf2,
                model_shortages=model_shortages_list, bom_lookup=bom_lookup
            )
            tcf1_total_alloc_df = pd.DataFrame(tcf1_tot_alloc)
            tcf2_total_alloc_df = pd.DataFrame(tcf2_tot_alloc)
            
        # 6. Trim & Model Mapping
        all_models_path = os.path.join(WORKSPACE_DIR, "All models.xlsx")
        if not os.path.exists(all_models_path):
            all_models_path = os.path.join(WORKSPACE_DIR, "TEST", "All models.xlsx")
        vc_to_desc, vc_to_trim = dl.load_all_models_catalog(all_models_path)
        
        def get_row_trim(row):
            s_desc = row.get('SALES DESCRIPTION', row.get('SALES DESC', None))
            m_name = row.get('Model', row.get('PRODUCT', ''))
            if s_desc and pd.notna(s_desc) and str(s_desc).strip() not in ['', 'nan']:
                return dl.extract_trim_from_sales_desc(s_desc, m_name)
            v_code = str(row.get('VEHICLE CODE', row.get('VC', ''))).strip()
            if v_code in vc_to_trim:
                return vc_to_trim[v_code]
            if v_code[:9] in vc_to_trim:
                return vc_to_trim[v_code[:9]]
            return "—"

        if not tcf1_alloc_df.empty:
            tcf1_alloc_df['Trim'] = tcf1_alloc_df.apply(get_row_trim, axis=1)
        if not tcf2_alloc_df.empty:
            tcf2_alloc_df['Trim'] = tcf2_alloc_df.apply(get_row_trim, axis=1)
            
        # Model mapping
        engine_to_model = dict(zip(st.session_state.engine_df['Engine Part No'].astype(str).str.strip(), st.session_state.engine_df['Model'])) if 'engine_df' in st.session_state and not st.session_state.engine_df.empty else {item['Engine Part No']: item['Model'] for item in ENGINE_DEFAULT_DATA}
        engine_to_model['546816111212'] = 'Punch EV (Nova)'
        engine_to_model['547380400103'] = 'Harrier EV'
        
        def map_row_model(df):
            if df is None or df.empty:
                return pd.Series(dtype='object')
            if 'Engine_Part' in df.columns:
                models_s = df['Engine_Part'].astype(str).str.strip().map(engine_to_model)
            else:
                models_s = pd.Series(dtype='object', index=df.index)
            models_s = pd.Series(models_s, index=df.index)
            is_missing = models_s.isna() | (models_s == '—') | (models_s == '')
            vc_col = 'VEHICLE CODE' if 'VEHICLE CODE' in df.columns else ('VC' if 'VC' in df.columns else None)
            if vc_col:
                vcs = df[vc_col].astype(str).str.strip()
                is_nova_vc = vcs.str.startswith('5468')
                is_harrier_ev_vc = vcs.str.startswith('5473')
                is_tayrona_vc = vcs.str.startswith('54831927A')
            else:
                is_nova_vc = pd.Series(False, index=df.index)
                is_harrier_ev_vc = pd.Series(False, index=df.index)
                is_tayrona_vc = pd.Series(False, index=df.index)
            if 'PRODUCT' in df.columns:
                is_tayrona = df['PRODUCT'].astype(str).str.strip().str.upper().str.contains('TAYRONA') | is_tayrona_vc
            else:
                is_tayrona = is_tayrona_vc
            res = np.where(is_tayrona, 'SAFARI EV',
                  np.where(is_nova_vc & is_missing, 'Punch EV (Nova)',
                  np.where(is_harrier_ev_vc & is_missing, 'Harrier EV', models_s)))
            return pd.Series(res, index=df.index).fillna('—')

        if not tcf1_alloc_df.empty:
            tcf1_alloc_df['Model'] = map_row_model(tcf1_alloc_df)
            tcf1_alloc_df['Cab location'] = tcf1_alloc_df.apply(ae.get_detailed_paint_summary_stage, axis=1)
        if not tcf2_alloc_df.empty:
            tcf2_alloc_df['Model'] = map_row_model(tcf2_alloc_df)
            tcf2_alloc_df['Cab location'] = tcf2_alloc_df.apply(ae.get_detailed_paint_summary_stage, axis=1)

        # 7. Stagewise Shortage & Missing BOM
        if float_df is not None and not float_df.empty:
            float_stages_df = ae.get_paint_float_stages(float_df)
            combined_true_stocks = {
                'engine': {**true_engine_tcf1, **true_engine_tcf2},
                'cockpit': {**true_cockpit_tcf1, **true_cockpit_tcf2},
                'wiring': {**true_wiring_tcf1, **true_wiring_tcf2}
            }
            shortage_report = ae.calculate_stagewise_shortage(float_stages_df, bom_df, combined_true_stocks, bom_lookup=bom_lookup)
            missing_bom_vcs = ae.find_missing_bom_vcs(float_df, bom_df)
        else:
            shortage_report = pd.DataFrame()
            missing_bom_vcs = pd.DataFrame()

        # Combined allocations and VGL for legacy page compatibility
        alloc_dfs = []
        if not tcf1_alloc_df.empty:
            alloc_dfs.append(tcf1_alloc_df)
        if not tcf2_alloc_df.empty:
            alloc_dfs.append(tcf2_alloc_df)
        alloc_results = pd.concat(alloc_dfs, ignore_index=True).to_dict('records') if alloc_dfs else []
        
        vgl_dfs = []
        if tcf1_drops is not None and not tcf1_drops.empty:
            vgl_dfs.append(tcf1_drops)
        if tcf2_drops is not None and not tcf2_drops.empty:
            vgl_dfs.append(tcf2_drops)
        vgl_df = pd.concat(vgl_dfs, ignore_index=True) if vgl_dfs else pd.DataFrame()

        # Build final DashboardData
        db_data = DashboardData(
            bom_df=bom_df if bom_df is not None else pd.DataFrame(),
            float_df=float_df if float_df is not None else pd.DataFrame(),
            vgl_df=vgl_df,
            alloc_results=alloc_results,
            paint_summary=paint_summary,
            paint_summary_vc_dict=paint_summary_vc,
            tcf1_drops=tcf1_drops,
            tcf2_drops=tcf2_drops,
            hourly_df=hourly_df,
            shop_totals=shop_totals,
            shop_vehicles_df=shop_vehicles_df,
            shop_ta_df=shop_ta_df,
            true_engine_tcf1=true_engine_tcf1,
            true_cockpit_tcf1=true_cockpit_tcf1,
            true_wiring_tcf1=true_wiring_tcf1,
            true_engine_tcf2=true_engine_tcf2,
            true_cockpit_tcf2=true_cockpit_tcf2,
            true_wiring_tcf2=true_wiring_tcf2,
            tcf1_alloc_df=tcf1_alloc_df,
            tcf2_alloc_df=tcf2_alloc_df,
            tcf1_final_stocks=tcf1_final_stocks,
            tcf2_final_stocks=tcf2_final_stocks,
            tcf1_total_alloc_df=tcf1_total_alloc_df,
            tcf2_total_alloc_df=tcf2_total_alloc_df,
            shortage_report=shortage_report,
            missing_bom_vcs=missing_bom_vcs,
            status="success"
        )
        
        st.session_state['dashboard_data'] = db_data
        st.session_state['dashboard_signature'] = current_signature
        st.session_state['_last_good_data'] = db_data
        
        return db_data

    except Exception as e:
        error_msg = f"Failed to load dashboard data: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        if st.session_state.get('_last_good_data') is not None:
            last_data = st.session_state['_last_good_data']
            last_data.status = "warning"
            last_data.error_message = error_msg
            return last_data
        return DashboardData(status="error", error_message=error_msg)
