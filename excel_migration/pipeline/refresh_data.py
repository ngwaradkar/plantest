"""
refresh_data.py
Phase 2 Orchestrator.
1. Reads settings from Excel
2. Finds latest files in the local data folder
3. Parses them using excel_data_loader.py
4. Writes the cleaned datasets back to the hidden helper sheets in TCF_PPC_Dashboard.xlsx
"""
import os
import glob
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import pandas as pd
import numpy as np
import datetime

import config
import excel_data_loader as dl

def get_latest_file(folder, pattern, exclude=None):
    """Finds the most recently modified file matching the pattern in the folder."""
    if not pattern: return None
    search_path = os.path.join(folder, pattern)
    files = glob.glob(search_path)
    
    if exclude:
        files = [f for f in files if exclude not in f]
        
    if not files:
        # Try finding anywhere in folder
        search_path = os.path.join(folder, f"*{pattern}*")
        files = glob.glob(search_path)
        if exclude:
            files = [f for f in files if exclude not in f]
            
    if not files: return None
    return max(files, key=os.path.getmtime)

def clear_sheet(ws, start_row=2):
    """Clears all data rows from a worksheet while preserving headers."""
    ws.delete_rows(start_row, ws.max_row)

def write_df_to_sheet(df, ws, start_row=2):
    """Writes a DataFrame to an openpyxl worksheet."""
    if df is None or df.empty: return
    
    # Ensure NaN is converted to None for openpyxl
    df = df.replace({pd.NA: None, np.nan: None})
    
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), start=start_row):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=value)

def run_refresh():
    print(f"[{datetime.datetime.now()}] Starting Excel Data Refresh...")
    settings = config.load_settings()
    data_folder = settings.get("Local Data Folder", r"D:\Dashboard Files")
    
    if not os.path.exists(data_folder):
        print(f"ERROR: Local Data Folder '{data_folder}' does not exist.")
        return
        
    print(f"Scanning folder: {data_folder}")
    
    # 1. Find Files
    files = {
        'BOM': get_latest_file(data_folder, settings.get('BOM File Name', 'Bom details.xlsx')),
        'FLOAT': get_latest_file(data_folder, settings.get('Float Report Pattern', 'PPC_Float_Report_*'), exclude='Paint'),
        'PAINT': get_latest_file(data_folder, settings.get('Paint Summary Pattern', 'PPC_Float_Report_Paint_*')),
        'VGL1': get_latest_file(data_folder, settings.get('TCF1 VGL Pattern', 'DPT_PLAN-VIN_GENERATION_REPORT_*')),
        'VGL2': get_latest_file(data_folder, settings.get('TCF2 VGL Pattern', 'TCF2_DPT-PLAN_VIN_GENERATION_REPORT_*')),
        'SHOP': get_latest_file(data_folder, settings.get('Shop Wise Pattern', 'Shop_Wise_Report_*')),
        'MASTER': get_latest_file(data_folder, settings.get('Dashboard Master File', 'Dashboard files.xlsm'))
    }
    
    for k, v in files.items():
        print(f"  {k}: {v or 'NOT FOUND'}")
        
    # If MASTER is found, we should ideally unpack it. 
    # For this standalone refresh, we will parse directly from the master if specific files are missing.
    master_path = files['MASTER']
    
    # 2. Load Data
    data = {}
    
    import logger
    import time

    # Float
    print("Loading Float Report...")
    if files['FLOAT']:
        try:
            t0 = time.time()
            data['FLOAT'] = dl.load_float_report(files['FLOAT'])
            logger.log_event("Data Loader", files['FLOAT'], "Success", "Float Report loaded", duration=round(time.time()-t0, 2))
        except Exception as e:
            logger.log_event("Data Loader", files['FLOAT'], "Error", "Float Report failed to load", str(e))
    elif not master_path:
        logger.log_event("Data Loader", "Float Report", "Critical", "Missing Float Report file")

    # Paint
    print("Loading Paint Summary...")
    if files['PAINT']:
        try:
            t0 = time.time()
            paint_dict = dl.load_paint_summary_report(files['PAINT'])
            if paint_dict:
                rows = []
                for model, stages in paint_dict.items():
                    row = {'MARKET': 'Domestic', 'PRODUCT FAMILY': '', 'SALES DESCRIPTION': '', 'SHORT VC': '', 'PACK': '-'}
                    row['PRODUCT FAMILY'] = model
                    row.update(stages)
                    rows.append(row)
                data['PAINT'] = pd.DataFrame(rows)
            logger.log_event("Data Loader", files['PAINT'], "Success", "Paint Summary loaded", duration=round(time.time()-t0, 2))
        except Exception as e:
            logger.log_event("Data Loader", files['PAINT'], "Error", "Paint Summary failed to load", str(e))
    elif not master_path:
        logger.log_event("Data Loader", "Paint Summary", "Error", "Missing Paint Summary file")

    # VGL
    print("Loading VGL Reports...")
    for vgl_key in ['VGL1', 'VGL2']:
        if files[vgl_key]:
            try:
                t0 = time.time()
                data[vgl_key] = dl.load_vgl(files[vgl_key])
                logger.log_event("Data Loader", files[vgl_key], "Success", f"{vgl_key} loaded", duration=round(time.time()-t0, 2))
            except Exception as e:
                logger.log_event("Data Loader", files[vgl_key], "Critical", f"{vgl_key} failed to load", str(e))
        else:
            logger.log_event("Data Loader", vgl_key, "Critical", f"Missing {vgl_key} file")

    # Shop & Hourly
    print("Loading Shop & Hourly Reports...")
    if files['SHOP']:
        try:
            t0 = time.time()
            totals, df_veh = dl.load_shop_wise_report(files['SHOP'])
            data['SHOP'] = df_veh
            logger.log_event("Data Loader", files['SHOP'], "Success", "Shop Wise loaded", duration=round(time.time()-t0, 2))
        except Exception as e:
            logger.log_event("Data Loader", files['SHOP'], "Error", "Shop Wise failed to load", str(e))
            
    if master_path:
        try:
            data['HOURLY'] = dl.load_hourly_production(master_path)
        except Exception as e:
            logger.log_event("Data Loader", "Master Workbook", "Error", "Hourly production failed to load", str(e))
        
    # 3. Write to Excel
    print("Writing to Excel workbook...")
    wb = openpyxl.load_workbook(config.EXCEL_PATH, keep_vba=True)
    
    if 'FLOAT' in data and data['FLOAT'] is not None:
        ws = wb['_RawFloat']
        clear_sheet(ws)
        write_df_to_sheet(data['FLOAT'], ws)
        print(f"  -> Wrote {len(data['FLOAT'])} rows to _RawFloat")
        
    if 'PAINT' in data and data['PAINT'] is not None:
        ws = wb['_RawPaint']
        clear_sheet(ws)
        write_df_to_sheet(data['PAINT'], ws)
        print(f"  -> Wrote {len(data['PAINT'])} rows to _RawPaint")
        
    if 'VGL1' in data and data['VGL1'] is not None:
        ws = wb['_RawVGL1']
        clear_sheet(ws)
        write_df_to_sheet(data['VGL1'], ws)
        print(f"  -> Wrote {len(data['VGL1'])} rows to _RawVGL1")
        
    if 'VGL2' in data and data['VGL2'] is not None:
        ws = wb['_RawVGL2']
        clear_sheet(ws)
        write_df_to_sheet(data['VGL2'], ws)
        print(f"  -> Wrote {len(data['VGL2'])} rows to _RawVGL2")
        
    if 'SHOP' in data and data['SHOP'] is not None:
        ws = wb['_RawShopWise']
        clear_sheet(ws)
        write_df_to_sheet(data['SHOP'], ws)
        print(f"  -> Wrote {len(data['SHOP'])} rows to _RawShopWise")
        
    if 'HOURLY' in data and data['HOURLY'] is not None:
        ws = wb['_RawHourly']
        clear_sheet(ws)
        write_df_to_sheet(data['HOURLY'], ws)
        print(f"  -> Wrote {len(data['HOURLY'])} rows to _RawHourly")
        
    # Write to Log
    ws_log = wb['Log']
    new_row = [datetime.datetime.now().strftime("%d-%m-%Y %I:%M %p"), "Data Refresh", "System", "Successfully refreshed data from local folder.", "✅"]
    ws_log.append(new_row)
    
    wb.save(config.EXCEL_PATH)
    print("Refresh complete.")

if __name__ == "__main__":
    import numpy as np
    run_refresh()
