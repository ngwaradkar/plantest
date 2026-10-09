"""
excel_paint_tcf_float.py
Phase 5: Paint Float and TCF Float calculations.
Uses python for data preparation of classifications, ensuring 100% parity with Streamlit.
Writes out formatted Excel Tables for Paint Float and TCF Float.
"""
import os
import sys
import pandas as pd
import sqlite3
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows

import config
import excel_data_loader as dl
import refresh_data as rd

APP_DIR = r"d:\Planner Dashboard"
if APP_DIR not in sys.path:
    sys.path.append(APP_DIR)
import allocation_engine as ae
import data_loader as dl_orig

def load_sqlite_data():
    db_path = os.path.join(APP_DIR, "clear_to_build.db")
    conn = sqlite3.connect(db_path)
    bom = pd.read_sql("SELECT short_vehicle_code, engine FROM bom_details", conn)
    bom_dict = {str(r['short_vehicle_code']).strip(): str(r['engine']).strip() for _, r in bom.iterrows()}
    
    engine_stocks = pd.read_sql("SELECT * FROM engine_stocks", conn)
    nova_stocks = pd.read_sql("SELECT * FROM nova_stocks", conn)
    conn.close()
    
    eng_dict = {}
    eng_ta = {}
    for _, r in engine_stocks.iterrows():
        part = str(r['engine_part_no']).strip()
        eng_dict[part] = int(r['clearance_qty'])
        eng_ta[part] = str(r['ta_code'])
        
    nova_dict = {}
    for _, r in nova_stocks.iterrows():
        nova_dict[str(r['Material']).strip()] = int(r['Clearance Qty'])
        
    return bom_dict, eng_dict, eng_ta, nova_dict

def get_tcf_drops(files_dict):
    tcf1 = pd.DataFrame()
    tcf2 = pd.DataFrame()
    if files_dict.get('VGL1'):
        tcf1 = dl.load_vgl(files_dict['VGL1'])
        if tcf1 is not None and not tcf1.empty:
            tcf1['Model'] = tcf1.get('SALES DESC', pd.Series(dtype=str)).apply(dl_orig.map_tcf_model_name)
    if files_dict.get('VGL2'):
        tcf2 = dl.load_vgl(files_dict['VGL2'])
        if tcf2 is not None and not tcf2.empty:
            tcf2['Model'] = tcf2.get('SALES DESC', pd.Series(dtype=str)).apply(dl_orig.map_tcf_model_name)
    return tcf1, tcf2

def get_today_vin_count(tcf_drops, model_name):
    if tcf_drops is None or tcf_drops.empty:
        return 0
    if 'Model' not in tcf_drops.columns:
        return len(tcf_drops)
    sub = tcf_drops[tcf_drops['Model'].astype(str).str.strip().str.upper() == model_name.upper()]
    if 'VIN_Count' in sub.columns:
        return int(sub['VIN_Count'].sum())
    return len(sub)

def get_today_vin_by_engine(tcf_drops, bom_dict):
    if tcf_drops is None or tcf_drops.empty:
        return {}
    eng_counts = {}
    for _, row in tcf_drops.iterrows():
        vc = row.get('VC')
        if pd.isna(vc): continue
        svc = str(vc).strip()[:9]
        eng = bom_dict.get(svc)
        if eng:
            cnt = int(row.get('VIN_Count', 1)) if pd.notna(row.get('VIN_Count')) else 1
            eng_counts[eng] = eng_counts.get(eng, 0) + cnt
    return eng_counts

def build_paint_float(float_df, paint_summary, tcf1_drops, tcf2_drops):
    tcf1_models = ['PUNCH', 'PUNCH EV', 'PUNCH Exports', 'NEXON']
    tcf2_models = ['HARRIER', 'HARRIER EV', 'SAFARI', 'SAFARI EV', 'NEXON']
    stages_list = [
        'PBS FLOAT', 'PBS TO POLISHING', 'POLISHING TO TOPCOAT', 
        'TOPCOAT TO WETSANDING G ROOFBLACK', 'TOPCOAT TO WETSANDING G FRESH', 
        'WETSANDING G TO SEALANT', 'PT ENTRY TO SEALANT', 'BIW LIFTING G TO PT', 'PT BYPASS'
    ]
    
    rows = []
    
    if paint_summary:
        # Use provided summary
        for model in tcf1_models:
            m_dict = paint_summary.get(model, {})
            row = {'Paint Float': 'TCF1', 'MODEL': model, 'Today VIN': get_today_vin_count(tcf1_drops, model)}
            for s in stages_list: row[s] = m_dict.get(s, 0)
            row['TOTAL UPTO SEALANT'] = m_dict.get('TOTAL UPTO SEALANT', sum(row[s] for s in stages_list[:6]))
            row['TOTAL FLOAT'] = m_dict.get('TOTAL FLOAT', row['TOTAL UPTO SEALANT'] + row['PT ENTRY TO SEALANT'] + row['BIW LIFTING G TO PT'] + row['PT BYPASS'])
            rows.append(row)
            
        tcf1_sub = {'Paint Float': 'TCF1', 'MODEL': 'TCF1 TOTAL', 'Today VIN': sum(r['Today VIN'] for r in rows)}
        for c in ['TOTAL FLOAT'] + stages_list + ['TOTAL UPTO SEALANT']: tcf1_sub[c] = sum(r[c] for r in rows)
        rows.append(tcf1_sub)
        
        tcf2_start = len(rows)
        for model in tcf2_models:
            m_dict = paint_summary.get(model, {})
            row = {'Paint Float': 'TCF2', 'MODEL': model, 'Today VIN': get_today_vin_count(tcf2_drops, model)}
            for s in stages_list: row[s] = m_dict.get(s, 0)
            row['TOTAL UPTO SEALANT'] = m_dict.get('TOTAL UPTO SEALANT', sum(row[s] for s in stages_list[:6]))
            row['TOTAL FLOAT'] = m_dict.get('TOTAL FLOAT', row['TOTAL UPTO SEALANT'] + row['PT ENTRY TO SEALANT'] + row['BIW LIFTING G TO PT'] + row['PT BYPASS'])
            rows.append(row)
            
        tcf2_sub = {'Paint Float': 'TCF2', 'MODEL': 'TCF2 TOTAL', 'Today VIN': sum(r['Today VIN'] for r in rows[tcf2_start:])}
        for c in ['TOTAL FLOAT'] + stages_list + ['TOTAL UPTO SEALANT']: tcf2_sub[c] = sum(r[c] for r in rows[tcf2_start:])
        rows.append(tcf2_sub)
        
    else:
        # Calculate from float
        if float_df is None or float_df.empty: return pd.DataFrame()
        
        # Add required columns
        stages_mapped = float_df.apply(ae.get_detailed_paint_summary_stage, axis=1)
        float_df['Stage'] = stages_mapped
        float_df['Model_Mapped'] = float_df['SALES DESCRIPTION'].apply(dl_orig.map_tcf_model_name)
        
        # TCF1
        tcf1_sub_df = float_df[float_df['SHOP'].astype(str).str.upper() == 'TCF1']
        for model in tcf1_models:
            model_df = tcf1_sub_df[tcf1_sub_df['Model_Mapped'] == model]
            row = {'Paint Float': 'TCF1', 'MODEL': model, 'Today VIN': get_today_vin_count(tcf1_drops, model)}
            tot = 0
            for s in stages_list:
                cnt = len(model_df[model_df['Stage'] == s])
                row[s] = cnt
                tot += cnt
            row['TOTAL FLOAT'] = tot
            row['TOTAL UPTO SEALANT'] = sum(row[s] for s in stages_list[:6])
            rows.append(row)
            
        tcf1_sub = {'Paint Float': 'TCF1', 'MODEL': 'TCF1 TOTAL', 'Today VIN': sum(r['Today VIN'] for r in rows)}
        for c in ['TOTAL FLOAT'] + stages_list + ['TOTAL UPTO SEALANT']: tcf1_sub[c] = sum(r[c] for r in rows)
        rows.append(tcf1_sub)
        
        # TCF2
        tcf2_start = len(rows)
        tcf2_sub_df = float_df[float_df['SHOP'].astype(str).str.upper() == 'TCF2']
        for model in tcf2_models:
            model_df = tcf2_sub_df[tcf2_sub_df['Model_Mapped'] == model]
            row = {'Paint Float': 'TCF2', 'MODEL': model, 'Today VIN': get_today_vin_count(tcf2_drops, model)}
            tot = 0
            for s in stages_list:
                cnt = len(model_df[model_df['Stage'] == s])
                row[s] = cnt
                tot += cnt
            row['TOTAL FLOAT'] = tot
            row['TOTAL UPTO SEALANT'] = sum(row[s] for s in stages_list[:6])
            rows.append(row)
            
        tcf2_sub = {'Paint Float': 'TCF2', 'MODEL': 'TCF2 TOTAL', 'Today VIN': sum(r['Today VIN'] for r in rows[tcf2_start:])}
        for c in ['TOTAL FLOAT'] + stages_list + ['TOTAL UPTO SEALANT']: tcf2_sub[c] = sum(r[c] for r in rows[tcf2_start:])
        rows.append(tcf2_sub)
        
    # Grand Total
    gt = {'Paint Float': 'GRAND TOTAL', 'MODEL': '', 'Today VIN': rows[tcf1_start-1 if 'tcf1_start' in locals() else len(tcf1_models)]['Today VIN'] + rows[-1]['Today VIN']}
    for c in ['TOTAL FLOAT'] + stages_list + ['TOTAL UPTO SEALANT']:
        gt[c] = rows[len(tcf1_models)][c] + rows[-1][c]
    rows.append(gt)
    
    return pd.DataFrame(rows)

def build_tcf_float(float_df, paint_summary_vc_dict, bom_dict, eng_stocks, eng_ta, nova_stocks, tcf1_drops, tcf2_drops):
    stages_upto_sealant = [
        'PBS FLOAT', 'PBS TO POLISHING', 'POLISHING TO TOPCOAT',
        'TOPCOAT TO WETSANDING G ROOFBLACK', 'TOPCOAT TO WETSANDING G FRESH',
        'WETSANDING G TO SEALANT'
    ]
    
    total_float_dict = {}
    pbs_float_dict = {}
    upto_sealant_dict = {}
    
    if paint_summary_vc_dict:
        for svc, counts in paint_summary_vc_dict.items():
            eng = bom_dict.get(svc)
            if eng and eng not in ['0', 'None', 'nan']:
                total_float_dict[eng] = total_float_dict.get(eng, 0) + counts.get('TOTAL FLOAT', 0)
                pbs_float_dict[eng] = pbs_float_dict.get(eng, 0) + counts.get('PBS FLOAT', 0)
                upto_sealant_dict[eng] = upto_sealant_dict.get(eng, 0) + counts.get('TOTAL UPTO SEALANT', 0)
    elif float_df is not None and not float_df.empty:
        vc_col = 'VEHICLE CODE' if 'VEHICLE CODE' in float_df.columns else 'VC'
        for _, row in float_df.iterrows():
            vc = row.get(vc_col)
            if pd.isna(vc): continue
            svc = str(vc).strip()[:9]
            eng = bom_dict.get(svc)
            if not eng or eng in ['0', 'None', 'nan']: continue
            
            stage = ae.get_detailed_paint_summary_stage(row)
            
            total_float_dict[eng] = total_float_dict.get(eng, 0) + 1
            if stage == 'PBS FLOAT': pbs_float_dict[eng] = pbs_float_dict.get(eng, 0) + 1
            if stage in stages_upto_sealant: upto_sealant_dict[eng] = upto_sealant_dict.get(eng, 0) + 1
            
    today_vin_dict = get_today_vin_by_engine(tcf1_drops, bom_dict)
    today_vin_dict2 = get_today_vin_by_engine(tcf2_drops, bom_dict)
    for k, v in today_vin_dict2.items(): today_vin_dict[k] = today_vin_dict.get(k, 0) + v
    
    rows = []
    
    # TCF1
    punch_parts = [
        ("54850000PTP001", "Punch MT SA"),
        ("54850000PTP002", "Punch AMT SA"),
        ("54970000PTP002", "Punch TC MCE"),
        ("54970000PTP003", "Punch MCE MT"),
        ("54970000PTP004", "Punch MCE AMT"),
        ("54970000PTP005", "Punch MCE CNG MT"),
        ("54970000PTP031", "Punch MCE CNG AMT")
    ]
    
    tcf1_vin_tot = 0; tcf1_pbs = 0; tcf1_seal = 0; tcf1_tot = 0
    for part, model in punch_parts:
        clr = eng_stocks.get(part, 0)
        vin = today_vin_dict.get(part, 0)
        bal = clr - vin
        pbs = pbs_float_dict.get(part, 0)
        seal = upto_sealant_dict.get(part, 0)
        tot = total_float_dict.get(part, 0)
        
        tcf1_vin_tot += vin; tcf1_pbs += pbs; tcf1_seal += seal; tcf1_tot += tot
        
        rows.append({
            'Engine Part No': part, 'Model': model, 'TA Code': eng_ta.get(part, ''),
            'Clearance After 6:30AM': clr, 'Today VIN': vin, 'Bal': bal,
            'PBS FLOAT': pbs, 'Float UPTO SEALANT': seal, 'TOTAL FLOAT': tot,
            'With respect to PBS FLOAT': bal - pbs,
            'With respect to Sealant FLOAT': bal - seal,
            'With respect to Total FLOAT': bal - tot
        })
        
    # Nova
    clr_nova = nova_stocks.get("Battery", 0)
    vin_nova = today_vin_dict.get("546816111212", 0)
    bal_nova = clr_nova - vin_nova
    pbs_nova = pbs_float_dict.get("546816111212", 0)
    seal_nova = upto_sealant_dict.get("546816111212", 0)
    tot_nova = total_float_dict.get("546816111212", 0)
    rows.append({
        'Engine Part No': '546816111212', 'Model': 'Punch EV', 'TA Code': '',
        'Clearance After 6:30AM': clr_nova, 'Today VIN': vin_nova, 'Bal': bal_nova,
        'PBS FLOAT': pbs_nova, 'Float UPTO SEALANT': seal_nova, 'TOTAL FLOAT': tot_nova,
        'With respect to PBS FLOAT': bal_nova - pbs_nova,
        'With respect to Sealant FLOAT': bal_nova - seal_nova,
        'With respect to Total FLOAT': bal_nova - tot_nova
    })
    
    # TCF2
    tcf2_parts = [
        ("572900000118", "Harrier / Safari Diesel AT"),
        ("572900000120", "Harrier / Safari Diesel MT"),
        ("54780000PTP001", "Harrier / Safari Petrol TGDI MT"),
        ("54780000PTP002", "Harrier / Safari Petrol TGDI AT")
    ]
    for part, model in tcf2_parts:
        clr = eng_stocks.get(part, 0)
        vin = today_vin_dict.get(part, 0)
        bal = clr - vin
        pbs = pbs_float_dict.get(part, 0)
        seal = upto_sealant_dict.get(part, 0)
        tot = total_float_dict.get(part, 0)
        
        rows.append({
            'Engine Part No': part, 'Model': model, 'TA Code': eng_ta.get(part, ''),
            'Clearance After 6:30AM': clr, 'Today VIN': vin, 'Bal': bal,
            'PBS FLOAT': pbs, 'Float UPTO SEALANT': seal, 'TOTAL FLOAT': tot,
            'With respect to PBS FLOAT': bal - pbs,
            'With respect to Sealant FLOAT': bal - seal,
            'With respect to Total FLOAT': bal - tot
        })
        
    return pd.DataFrame(rows)

def write_table_data(ws, df, start_row, clear=True):
    if clear:
        ws.delete_rows(start_row, max(ws.max_row, start_row + 1))
    if df is None or df.empty: return
    df = df.where(pd.notnull(df), None)
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), start=start_row):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=value)

def run_phase5():
    print("Starting Phase 5: Paint & TCF Float Summaries...")
    settings = config.load_settings()
    data_folder = settings.get("Local Data Folder", r"D:\Dashboard Files")
    
    files = {
        'FLOAT': rd.get_latest_file(data_folder, settings.get('Float Report Pattern', 'PPC_Float_Report_*'), exclude='Paint'),
        'VGL1': rd.get_latest_file(data_folder, settings.get('TCF1 VGL Pattern', 'DPT_PLAN-VIN_GENERATION_REPORT_*')),
        'VGL2': rd.get_latest_file(data_folder, settings.get('TCF2 VGL Pattern', 'TCF2_DPT-PLAN_VIN_GENERATION_REPORT_*')),
        'PAINT': rd.get_latest_file(data_folder, 'PPC_Float_Report_Paint*')
    }
    
    bom_dict, eng_stocks, eng_ta, nova_stocks = load_sqlite_data()
    tcf1_drops, tcf2_drops = get_tcf_drops(files)
    
    df_float = dl.load_float_report(files['FLOAT']) if files['FLOAT'] else pd.DataFrame()
    paint_summary = None
    paint_summary_vc = None
    
    # if files['PAINT']:
    #    paint_summary = dl.load_paint_summary_report(files['PAINT'])
    #    paint_summary_vc = dl.load_paint_summary_by_vc(files['PAINT'])
        
    print("Building Paint Float Summary...")
    df_paint = build_paint_float(df_float, paint_summary, tcf1_drops, tcf2_drops)
    
    print("Building TCF Float (Engine Shortage) Summary...")
    df_tcf = build_tcf_float(df_float, paint_summary_vc, bom_dict, eng_stocks, eng_ta, nova_stocks, tcf1_drops, tcf2_drops)
    
    print("Writing to Excel...")
    wb = openpyxl.load_workbook(config.EXCEL_PATH, keep_vba=True)
    
    if 'Paint Float' not in wb.sheetnames:
        wb.create_sheet('Paint Float')
    if 'TCF Float' not in wb.sheetnames:
        wb.create_sheet('TCF Float')
        
    # Paint float writes over tblPaintFloat in phase1 sheet
    write_table_data(wb['Paint Float'], df_paint, 3)
    
    # TCF float writes over tblTCFFloat
    write_table_data(wb['TCF Float'], df_tcf, 3)
    
    # Add Formulas for clarity in TCF Float sheet
    ws_tcf = wb['TCF Float']
    for r in range(3, 3 + len(df_tcf)):
        ws_tcf.cell(row=r, column=6).value = "=[@[Clearance After 6:30AM]]-[@[Today VIN]]"
        ws_tcf.cell(row=r, column=10).value = "=[@Bal]-[@[PBS FLOAT]]"
        ws_tcf.cell(row=r, column=11).value = "=[@Bal]-[@[Float UPTO SEALANT]]"
        ws_tcf.cell(row=r, column=12).value = "=[@Bal]-[@[TOTAL FLOAT]]"
        
    wb.save(config.EXCEL_PATH)
    print("Phase 5 complete.")

if __name__ == "__main__":
    run_phase5()
