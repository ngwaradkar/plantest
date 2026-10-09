"""
config.py
Reads configuration settings directly from the TCF_PPC_Dashboard.xlsx Settings sheet.
"""
import openpyxl
import os

base_path = r"d:\Planner Dashboard\excel_migration\TCF_PPC_Dashboard"
if os.path.exists(base_path + ".xlsm"):
    EXCEL_PATH = base_path + ".xlsm"
else:
    EXCEL_PATH = base_path + ".xlsx"

def load_settings():
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(f"Dashboard Excel file not found at {EXCEL_PATH}")
        
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    if "Settings" not in wb.sheetnames:
        raise ValueError("Settings sheet not found in dashboard workbook.")
        
    ws = wb["Settings"]
    settings = {}
    
    for row in ws.iter_rows(min_row=4, max_col=2, values_only=True):
        key = str(row[0] or "").strip()
        val = str(row[1] or "").strip()
        
        # Skip section headers and empty keys
        if not key or key.startswith(chr(0x1F4)) or key.startswith(chr(0x2699)) or key.startswith("📊") or key.startswith("🚗") or key.startswith("📱"):
            continue
            
        settings[key] = val
        
    wb.close()
    return settings

if __name__ == "__main__":
    print("Loading settings...")
    s = load_settings()
    for k, v in s.items():
        print(f"{k}: {v}")
