"""
excel_data_loader.py
Phase 2: Streamlit-free Python Data Loader for Excel Migration.
Reproduces all parsing logic, HTML-disguised XLS detection, forward-filling,
and dynamic column mapping from data_loader.py, but outputs to Excel instead of Streamlit.
"""
import pandas as pd
import numpy as np
import io
import re
import urllib.request
import os
import openpyxl
from datetime import datetime

# ==========================================
# 1. HELPER / CLEANING FUNCTIONS
# ==========================================
def clean_part_number(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    if not val_str or val_str.isspace():
        return None
    return val_str

def _detect_html_content(filepath_or_buffer):
    """Detects HTML-disguised XLS files and fixes rowspan/colspan=0 bugs."""
    try:
        is_html = False
        html_content = None
        
        if hasattr(filepath_or_buffer, 'read'):
            pos = filepath_or_buffer.tell()
            filepath_or_buffer.seek(0)
            sample = filepath_or_buffer.read(500)
            if isinstance(sample, bytes):
                sample = sample.decode('utf-8', errors='ignore')
            
            if '<html' in sample.lower() or '<style' in sample.lower() or '<table' in sample.lower():
                is_html = True
                filepath_or_buffer.seek(0)
                full_content = filepath_or_buffer.read()
                if isinstance(full_content, bytes):
                    html_content = full_content.decode('utf-8', errors='ignore')
                else:
                    html_content = full_content
                    
                # Fix HTML rowspan=0 bug that breaks pd.read_html
                html_content = re.sub(r'(rowspan|colspan)\s*=\s*"0"', r'\1="1"', html_content, flags=re.IGNORECASE)
                html_content = re.sub(r"(rowspan|colspan)\s*=\s*'0'", r"\1='1'", html_content, flags=re.IGNORECASE)
            
            filepath_or_buffer.seek(pos)
        else:
            with open(filepath_or_buffer, 'rb') as f:
                sample = f.read(500).decode('utf-8', errors='ignore')
                if '<html' in sample.lower() or '<style' in sample.lower() or '<table' in sample.lower():
                    is_html = True
                    f.seek(0)
                    html_content = f.read().decode('utf-8', errors='ignore')
                    html_content = re.sub(r'(rowspan|colspan)\s*=\s*"0"', r'\1="1"', html_content, flags=re.IGNORECASE)
                    html_content = re.sub(r"(rowspan|colspan)\s*=\s*'0'", r"\1='1'", html_content, flags=re.IGNORECASE)
                    
        return is_html, html_content
    except Exception as e:
        print(f"Error in _detect_html_content: {e}")
        return False, None

def _extract_date_tuple(filename):
    if not isinstance(filename, str):
        return (0, 0, 0)
    m = re.search(r'(\d{2})[_\-](\d{2})[_\-](\d{4})', filename)
    if m:
        try:
            return (int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except:
            pass
    return (0, 0, 0)

# ==========================================
# 2. CORE PARSERS
# ==========================================
def load_bom(filepath_or_buffer):
    """Loads BOM. Required cols: Short Vehicle Code, Front Wiring, Cockpit, Engine."""
    try:
        if isinstance(filepath_or_buffer, str) and filepath_or_buffer.endswith('.db'):
            # SQLite fallback
            import sqlite3
            conn = sqlite3.connect(filepath_or_buffer)
            df = pd.read_sql("SELECT short_vehicle_code as 'Short Vehicle Code', front_wiring as 'Front Wiring', cockpit as 'Cockpit', engine as 'Engine' FROM bom_details", conn)
            conn.close()
            return df

        df = pd.read_excel(filepath_or_buffer, engine='openpyxl')
        df.columns = [str(c).strip() for c in df.columns]
        
        req_cols = ['Short Vehicle Code', 'Front Wiring', 'Cockpit', 'Engine']
        for r in req_cols:
            if r not in df.columns:
                for c in df.columns:
                    if r.lower() in str(c).lower():
                        df.rename(columns={c: r}, inplace=True)
                        break
        
        missing = [c for c in req_cols if c not in df.columns]
        if missing:
            raise ValueError(f"BOM missing columns: {missing}")
            
        df = df.dropna(subset=['Short Vehicle Code'])
        df['Short Vehicle Code'] = df['Short Vehicle Code'].astype(str).str.strip()
        df['Front Wiring'] = df['Front Wiring'].apply(clean_part_number)
        df['Cockpit'] = df['Cockpit'].apply(clean_part_number)
        df['Engine'] = df['Engine'].apply(clean_part_number)
        df = df.drop_duplicates(subset=['Short Vehicle Code'], keep='first')
        return df[req_cols].copy()
    except Exception as e:
        import logger
        logger.log_event("Data Loader", filepath, "Error", "Error loading BOM", str(e))
        return pd.DataFrame()

def load_float_report(filepath_or_buffer):
    """Loads PPC Float Report (Cabs in paint shop). Handles HTML, duplicate BIWs (hold aggregation)."""
    try:
        is_html, html_content = _detect_html_content(filepath_or_buffer)
        
        if is_html and html_content:
            dfs = pd.read_html(io.StringIO(html_content))
            if not dfs: return None
            df = dfs[0]
            df.columns = [str(c).strip() for c in df.iloc[0]]
            df = df[1:].reset_index(drop=True)
        else:
            try:
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            except:
                df = pd.read_excel(filepath_or_buffer)
                
        df.columns = [str(c).strip() for c in df.columns]
        
        for c in df.columns:
            if c.lower() in ['vc', 'vehicle_code', 'vehicle code']:
                df.rename(columns={c: 'VEHICLE CODE'}, inplace=True)
                break
                
        df['VC'] = df['VEHICLE CODE']
        
        date_cols = ['BIW LIFTING', 'PTCED', 'SEALANT', 'TOPCOAT', 'PBS LIFT']
        for dc in date_cols:
            if dc in df.columns:
                df[dc] = pd.to_datetime(df[dc], format='mixed', dayfirst=True, errors='coerce')
                
        if 'BIW NUMBER' in df.columns:
            df['BIW NUMBER'] = df['BIW NUMBER'].apply(lambda x: str(int(x)) if pd.notna(x) and str(x).strip().replace('.0','').isdigit() else str(x).strip() if pd.notna(x) else np.nan)
            
            # Multi-hold aggregation
            def agg_holds(group):
                res = group.iloc[0].to_dict()
                if len(group) > 1:
                    holds = [str(h).strip() for h in group['HOLD BY'] if pd.notna(h) and str(h).strip() not in ['', 'nan']]
                    reasons = [str(r).strip() for r in group['REASONS S'] if pd.notna(r) and str(r).strip() not in ['', 'nan']]
                    if holds:
                        res['HOLD BY'] = ', '.join(list(dict.fromkeys(holds)))
                    if reasons:
                        res['REASONS S'] = ', '.join(list(dict.fromkeys(reasons)))
                return pd.Series(res)
                
            if not df.empty:
                df = df.groupby('BIW NUMBER', as_index=False, dropna=False).apply(agg_holds).reset_index(drop=True)
                
        return df
    except Exception as e:
        import logger
        logger.log_event("Data Loader", filepath_or_buffer, "Error", "Error loading Float Report", str(e))
        return pd.DataFrame()

def load_paint_summary_report(filepath_or_buffer):
    """Loads Paint Float Summary, returning dict[model][stage] counts."""
    try:
        is_html, html_content = _detect_html_content(filepath_or_buffer)
        if is_html and html_content:
            dfs = pd.read_html(io.StringIO(html_content))
            df = dfs[0]
        else:
            df = pd.read_excel(filepath_or_buffer)
            
        # Find header row
        header_idx = -1
        for i in range(min(10, len(df))):
            row_vals = [str(x).upper().strip() for x in df.iloc[i].values if pd.notna(x)]
            if any('TOTAL FLOAT' in x for x in row_vals):
                header_idx = i
                break
                
        if header_idx >= 0:
            cols = [str(x).upper().strip() if pd.notna(x) else f"Unnamed_{j}" for j, x in enumerate(df.iloc[header_idx].values)]
            df.columns = cols
            df = df.iloc[header_idx+1:].reset_index(drop=True)
        else:
            df.columns = [str(c).upper().strip() for c in df.columns]
            
        # Stage mapping
        stage_names = [
            'TOTAL FLOAT', 'PBS FLOAT', 'PBS TO POLISHING', 'POLISHING TO TOPCOAT',
            'TOPCOAT TO WETSANDING G ROOFBLACK', 'TOPCOAT TO WETSANDING G FRESH',
            'WETSANDING G TO SEALANT', 'TOTAL UPTO SEALANT',
            'PT ENTRY TO SEALANT', 'BIW LIFTING G TO PT', 'PT BYPASS'
        ]
        
        col_map = {}
        for c in df.columns:
            c_up = c.upper()
            if 'ROOF' in c_up or 'BLACK' in c_up: col_map['TOPCOAT TO WETSANDING G ROOFBLACK'] = c
            elif 'WETSANDING' in c_up and 'SEAL' in c_up: col_map['WETSANDING G TO SEALANT'] = c
            elif 'UPTO SEALANT' in c_up or 'UPTO SEALENT' in c_up: col_map['TOTAL UPTO SEALANT'] = c
            else:
                for sn in stage_names:
                    if sn in c_up and sn not in col_map:
                        col_map[sn] = c
                        break
                        
        if len(col_map) < 5:
            # Fallback indices
            default_indices = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
            for i, sn in enumerate(stage_names):
                if i < len(default_indices) and default_indices[i] < len(df.columns):
                    col_map[sn] = df.columns[default_indices[i]]

        pf_map = {'HORNBILL': 'PUNCH', 'NOVA': 'PUNCH.EV', 'ETURNA': 'HARRIER.EV', 
                  'GRAVITAS': 'SAFARI', 'Q5': 'HARRIER', 'TAYRONA': 'SAFARI.EV'}
        
        target_models = ['PUNCH', 'PUNCH.EV', 'HARRIER.EV', 'SAFARI', 'HARRIER', 'SAFARI.EV']
        result = {m: {s: 0 for s in stage_names} for m in target_models}
        
        for idx, row in df.iterrows():
            row_str = ' '.join([str(x).upper() for x in row.values if pd.notna(x)])
            if 'TOTAL' in row_str and not 'GRAND' in row_str and not 'SUB' in row_str:
                matched_model = None
                for pf_key, model_val in pf_map.items():
                    if pf_key in row_str or model_val in row_str:
                        matched_model = model_val
                        break
                if matched_model:
                    for s in stage_names:
                        if s in col_map:
                            try:
                                val = str(row[col_map[s]]).strip()
                                result[matched_model][s] = int(float(val)) if val and val.replace('.','',1).isdigit() else 0
                            except:
                                pass
        return result
    except Exception as e:
        import logger
        logger.log_event("Data Loader", filepath_or_buffer, "Error", "Error loading Paint Summary", str(e))
        return None

def load_vgl(filepath_or_buffer):
    """Loads VGL/DPT Plan report (VIN generation). HTML BeautifulSoup parsing for missing headers."""
    try:
        is_html, html_content = _detect_html_content(filepath_or_buffer)
        df = None
        
        if is_html and html_content:
            html_upper = html_content.upper()
            if ('PRODUCTFAMILY' in html_upper or 'PRODUCT FAMILY' in html_upper) and 'SR NO' not in html_upper:
                # Custom BeautifulSoup parser for difficult DPT Plan HTML
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                rows = soup.find_all('tr')
                data = []
                current_pf = None
                for tr in rows:
                    tds = tr.find_all(['td', 'th'])
                    if len(tds) >= 6:
                        market = tds[0].get_text(strip=True)
                        pf = tds[1].get_text(strip=True)
                        vc = tds[2].get_text(strip=True)
                        sales_desc = tds[3].get_text(strip=True)
                        plan = tds[4].get_text(strip=True)
                        vin_str = tds[5].get_text(strip=True)
                        
                        if not vin_str.isdigit() and plan.isdigit():
                            vin_str = plan
                            
                        if pf: current_pf = pf
                        if not current_pf: current_pf = pf
                        
                        if vc.upper() not in ['TOTAL', 'GRAND TOTAL'] and market.upper() not in ['TOTAL', 'GRAND TOTAL']:
                            data.append({
                                'MARKET': market, 'ProductFamily': current_pf, 'VC': vc,
                                'SALES_DESC': sales_desc, 'Plan': plan, 'VIN': vin_str
                            })
                if data:
                    df = pd.DataFrame(data)
            
            if df is None:
                dfs = pd.read_html(io.StringIO(html_content))
                if dfs:
                    df = dfs[0]
                    df.columns = [str(c).strip() for c in df.iloc[0]]
                    df = df[1:].reset_index(drop=True)
        
        if df is None:
            try:
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            except:
                df = pd.read_excel(filepath_or_buffer)
                
        if df is None or df.empty: return None
        
        df.columns = [str(c).strip() for c in df.columns]
        
        aliases = {'SHORT VEHICLE CODE': 'VEHICLE CODE', 'FULL VC': 'VEHICLE CODE', 'VC': 'VEHICLE CODE', 'VEHICLE_CODE': 'VEHICLE CODE'}
        for c in df.columns:
            if c.upper() in aliases:
                df.rename(columns={c: aliases[c.upper()]}, inplace=True)
                break
                
        if 'VEHICLE CODE' not in df.columns and 'VC' in df.columns:
            df['VEHICLE CODE'] = df['VC']
        elif 'VEHICLE CODE' in df.columns and 'VC' not in df.columns:
            df['VC'] = df['VEHICLE CODE']
            
        if 'BIW NUMBER' in df.columns:
            df['BIW NUMBER'] = df['BIW NUMBER'].apply(lambda x: str(int(float(x))) if pd.notna(x) and str(x).strip().replace('.0','').replace('e+','').replace('+','').isdigit() else str(x).strip())
            
        # Model mapping
        pf_map = {'HORNBILL': 'PUNCH', 'NOVA': 'PUNCH.EV', 'ETURNA': 'HARRIER.EV', 
                  'GRAVITAS': 'SAFARI', 'Q5': 'HARRIER', 'TAYRONA': 'SAFARI.EV'}
        
        def map_model(row):
            vc = str(row.get('VC', '')).strip().upper()
            if vc == '54831927A': return 'SAFARI EV'
            sd = str(row.get('SALES DESCRIPTION', row.get('SALES_DESC', ''))).upper()
            pf = str(row.get('ProductFamily', row.get('PRODUCT FAMILY', ''))).upper()
            comb = sd + " " + pf
            
            if 'NOVA' in comb or 'PUNCH.EV' in comb or 'PUNCH EV' in comb: return 'PUNCH.EV'
            if 'HORNBILL' in comb or 'PUNCH' in comb: return 'PUNCH'
            if 'ETURNA' in comb or 'HARRIER.EV' in comb or 'HARRIER EV' in comb: return 'HARRIER.EV'
            if 'TAYRONA' in comb or 'SAFARI.EV' in comb or 'SAFARI EV' in comb: return 'SAFARI.EV'
            if 'GRAVITAS' in comb or 'SAFARI' in comb: return 'SAFARI'
            if 'Q5' in comb or 'HARRIER' in comb: return 'HARRIER'
            
            for k, v in pf_map.items():
                if k in comb: return v
            return 'UNKNOWN'
            
        df['Model_Family'] = df.apply(map_model, axis=1)
        
        # Extract VIN Count
        vin_col = None
        candidates = ['TCF/-VIN', 'TCF2-VIN', 'TCF-VIN', 'TCF1-VIN', 'TCF1_VIN', 'TCF2_VIN', 'VIN_COUNT', 'TODAY VIN', 'VIN GENERATION', 'VIN', 'VIN QTY', 'VIN_QTY']
        for c in df.columns:
            if str(c).upper().strip() in candidates:
                vin_col = c
                break
        
        df['VIN_Count'] = pd.to_numeric(df[vin_col], errors='coerce').fillna(0).astype(int) if vin_col else 0
        
        return df
    except Exception as e:
        import logger; logger.log_event("Data Loader", filepath_or_buffer, "Error", "Error loading VGL", str(e))
        return None

def load_stock_grouped(filepath_or_buffer, sheet_name, vc_col_idx, part_col_idx, qty_col_idx, skip_rows=2):
    """Parses grouped Cockpit/Wiring stock reports with forward-filling VC."""
    try:
        is_html, html_content = _detect_html_content(filepath_or_buffer)
        if is_html and html_content:
            dfs = pd.read_html(io.StringIO(html_content))
            df = dfs[0] if dfs else None
        else:
            try:
                df = pd.read_excel(filepath_or_buffer, sheet_name=sheet_name, engine='pyxlsb', header=None)
            except:
                try:
                    df = pd.read_excel(filepath_or_buffer, sheet_name=sheet_name, engine='openpyxl', header=None)
                except:
                    df = pd.read_excel(filepath_or_buffer, sheet_name=sheet_name, header=None)
                    
        if df is None or df.empty: return {}, {}
        
        df = df.iloc[skip_rows:]
        part_to_qty = {}
        vc_to_part = {}
        
        current_part = None
        current_qty = 0
        
        for idx, row in df.iterrows():
            part = row.iloc[part_col_idx] if part_col_idx < len(row) else None
            qty = row.iloc[qty_col_idx] if qty_col_idx < len(row) else None
            vc = row.iloc[vc_col_idx] if vc_col_idx < len(row) else None
            
            clean_part = clean_part_number(part)
            if clean_part:
                current_part = clean_part
                try:
                    current_qty = int(float(str(qty).strip()))
                except:
                    current_qty = 0
                part_to_qty[current_part] = current_qty
                
            if pd.notna(vc) and current_part:
                vc_str = str(vc).strip()
                if vc_str.endswith('.0'): vc_str = vc_str[:-2]
                if len(vc_str) >= 8 and vc_str[0].isdigit():
                    vc_to_part[vc_str] = current_part
                    
        return part_to_qty, vc_to_part
    except Exception as e:
        import logger; logger.log_event("Data Loader", filepath_or_buffer, "Error", f"Error loading Stock Grouped ({sheet_name})", str(e))
        return {}, {}

def load_shop_wise_report(filepath_or_buffer):
    """Loads Shop Wise report (plant totals)."""
    try:
        is_html, html_content = _detect_html_content(filepath_or_buffer)
        df = None
        if is_html and html_content:
            dfs = pd.read_html(io.StringIO(html_content))
            df = dfs[0] if dfs else None
        else:
            try:
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            except:
                df = pd.read_excel(filepath_or_buffer)
                
        if df is None: return None, None
        
        # Find header
        header_idx = -1
        for i in range(min(10, len(df))):
            row_str = ' '.join([str(x).upper() for x in df.iloc[i].values if pd.notna(x)])
            if 'TCF' in row_str and 'VIN' in row_str and 'PAINT' in row_str:
                header_idx = i
                break
                
        if header_idx < 0: return None, None
        
        df.columns = [str(c).upper().strip() for c in df.iloc[header_idx].values]
        
        # Totals row is immediately after header
        totals_row = df.iloc[header_idx + 1]
        totals_dict = {}
        for c in df.columns:
            if pd.notna(totals_row.get(c)):
                try:
                    totals_dict[c] = int(float(str(totals_row[c]).strip()))
                except:
                    pass
                    
        # Parse vehicle rows
        data_rows = df.iloc[header_idx + 2:]
        vehicles = []
        
        for idx, row in data_rows.iterrows():
            model = str(row.iloc[0]).strip()
            if model.lower() in ['nan', 'none', 'total', 'model', '']: continue
            if model.isdigit(): continue # TA code
            
            # Map model (filter non-TCF)
            model_up = model.upper()
            mapped = None
            if 'HORNBILL' in model_up or 'PUNCH' in model_up:
                if 'EXP' in model_up: mapped = 'PUNCH Exports'
                elif 'EV' in model_up or 'NOVA' in model_up: mapped = 'PUNCH EV'
                else: mapped = 'PUNCH'
            elif 'NOVA' in model_up: mapped = 'PUNCH EV'
            elif 'ETURNA' in model_up: mapped = 'HARRIER EV'
            elif 'GRAVITAS' in model_up or 'SAFARI' in model_up:
                if 'EV' in model_up: mapped = 'SAFARI EV'
                else: mapped = 'SAFARI'
            elif 'Q5' in model_up or 'HARRIER' in model_up:
                if 'EV' in model_up or 'ETURNA' in model_up: mapped = 'HARRIER EV'
                else: mapped = 'HARRIER'
            
            if mapped:
                vehicles.append({
                    'Model': model,
                    'Mapped Model': mapped,
                    'TCF VIN': pd.to_numeric(row.get('TCF VIN', 0), errors='coerce') or 0,
                    'TCF2 VIN': pd.to_numeric(row.get('TCF2 VIN', 0), errors='coerce') or 0,
                    'TCF DROP': pd.to_numeric(row.get('TCF DROP', 0), errors='coerce') or 0,
                    'TCF2 DROP': pd.to_numeric(row.get('TCF2 DROP', 0), errors='coerce') or 0,
                    'PAINT': pd.to_numeric(row.get('PAINT', 0), errors='coerce') or 0,
                    'T60': pd.to_numeric(row.get('T60', 0), errors='coerce') or 0,
                    'T40': pd.to_numeric(row.get('T40', 0), errors='coerce') or 0,
                })
                
        df_vehicles = pd.DataFrame(vehicles) if vehicles else pd.DataFrame()
        return totals_dict, df_vehicles
    except Exception as e:
        import logger; logger.log_event("Data Loader", filepath_or_buffer, "Error", "Error loading Shop Wise", str(e))
        return None, None

def load_hourly_production(filepath_or_buffer):
    """Loads Hourly Production grid."""
    try:
        try:
            df = pd.read_excel(filepath_or_buffer, engine='pyxlsb', sheet_name=None)
        except:
            df = pd.read_excel(filepath_or_buffer, sheet_name=None)
            
        target_sheet = list(df.keys())[0]
        for sn in df.keys():
            if 'hourly' in sn.lower() or 'production' in sn.lower():
                target_sheet = sn
                break
                
        df = df[target_sheet]
        
        # Find header
        header_idx = -1
        for i in range(min(10, len(df))):
            row_str = ' '.join([str(x).upper() for x in df.iloc[i].values if pd.notna(x)])
            if 'ACHIEVEMENT' in row_str or 'POINT' in row_str or 'STAGE' in row_str:
                header_idx = i
                break
                
        if header_idx < 0: return None
        
        df.columns = [str(c).upper().strip() for c in df.iloc[header_idx].values]
        df = df.iloc[header_idx+1:].reset_index(drop=True)
        
        # Remove SR NO
        cols = list(df.columns)
        if re.match(r'^(SR\.?\s*NO|S\.?\s*NO)$', cols[0], re.I):
            df = df.drop(columns=[cols[0]])
            
        df.rename(columns={df.columns[0]: 'ACHIEVEMENT POINT'}, inplace=True)
        
        target_pts = ['TCF1_VIN_GENERATION', 'TCF2_VIN_GENERATION', 'TCF1-DROP', 'TCF2-DROP']
        rows = []
        for pt in target_pts:
            norm_pt = re.sub(r'[^A-Z0-9]', '', pt)
            found = False
            for idx, row in df.iterrows():
                val = str(row.iloc[0]).upper()
                norm_val = re.sub(r'[^A-Z0-9]', '', val)
                if norm_pt in norm_val:
                    r_dict = row.to_dict()
                    r_dict['ACHIEVEMENT POINT'] = pt
                    rows.append(r_dict)
                    found = True
                    break
            if not found:
                rows.append({'ACHIEVEMENT POINT': pt})
                
        return pd.DataFrame(rows)
    except Exception as e:
        import logger; logger.log_event("Data Loader", master_wb_path, "Error", "Error loading Hourly Production", str(e))
        return None
