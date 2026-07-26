import pandas as pd
import numpy as np
import io
import re
import os
import openpyxl
import pyxlsb
import sqlite3

def clean_part_number(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    # If the string is empty or just whitespace or '0', return None or '0'
    if not val_str or val_str.isspace():
        return None
    return val_str

def _detect_html_content(filepath_or_buffer):
    """
    Detects whether a file (given as an on-disk path string OR an in-memory
    file-like buffer, e.g. a Streamlit UploadedFile returned by
    st.file_uploader) is actually an HTML table disguised with an .xls
    extension -- a common export format from plant reporting systems (PPC,
    DPT Plan, etc). This works identically for both cases, so uploads made
    through the browser file uploader are detected the same way as files
    picked up automatically from disk.

    Returns (is_html: bool, html_content: str or None). Buffers are left at
    position 0 afterwards so downstream code can still read them.
    """
    name = filepath_or_buffer if isinstance(filepath_or_buffer, str) else getattr(filepath_or_buffer, 'name', '')
    ext = os.path.splitext(str(name).lower())[1]

    # Real .xlsx/.xlsb files are binary zip archives and are never HTML, so
    # only bother sniffing content for extensions that plant systems are
    # known to mislabel (.xls/.html/.htm), or when we don't know the name.
    if ext not in ['.xls', '.html', '.htm', '']:
        return False, None

    try:
        if isinstance(filepath_or_buffer, str):
            with open(filepath_or_buffer, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        else:
            filepath_or_buffer.seek(0)
            raw = filepath_or_buffer.read()
            filepath_or_buffer.seek(0)
            content = raw.decode('utf-8', errors='ignore') if isinstance(raw, bytes) else raw
    except Exception:
        return False, None

    first_chars = content[:500].lower()
    if '<html' in first_chars or '<style' in first_chars or '<table' in first_chars:
        return True, content
    return False, None

def load_bom(filepath_or_buffer):
    """
    Loads BOM details.xlsx and returns a cleaned DataFrame.
    Expected columns: 'Short Vehicle Code', 'Front Wiring', 'Cockpit ', 'Engine'
    """
    if not isinstance(filepath_or_buffer, str):
        try:
            filepath_or_buffer.seek(0)
        except Exception:
            pass
    # openpyxl engine is used for .xlsx
    df = pd.read_excel(filepath_or_buffer, engine='openpyxl')
    
    # Strip whitespace from headers
    df.columns = [str(c).strip() for c in df.columns]
    
    # Required columns check
    req = ['Short Vehicle Code', 'Front Wiring', 'Cockpit', 'Engine']
    for r in req:
        if r not in df.columns:
            # Check with partial match
            matched_col = [c for c in df.columns if r.lower() in c.lower()]
            if matched_col:
                df.rename(columns={matched_col[0]: r}, inplace=True)
            else:
                raise ValueError(f"Required BOM column '{r}' not found. Available: {list(df.columns)}")
                
    # Keep only target columns and clean data
    df = df[['Short Vehicle Code', 'Front Wiring', 'Cockpit', 'Engine']].copy()
    df.dropna(subset=['Short Vehicle Code'], inplace=True)
    
    # Clean part numbers and vehicle codes
    df['Short Vehicle Code'] = df['Short Vehicle Code'].astype(str).str.strip()
    df['Front Wiring'] = df['Front Wiring'].apply(clean_part_number)
    df['Cockpit'] = df['Cockpit'].apply(clean_part_number)
    df['Engine'] = df['Engine'].apply(clean_part_number)
    
    # Deduplicate by Short Vehicle Code
    df.drop_duplicates(subset=['Short Vehicle Code'], keep='first', inplace=True)
    return df

def load_float_report(filepath_or_buffer):
    """
    Loads PPC Float Report (which can be .xlsb or .xls disguised HTML) and returns a cleaned DataFrame.
    Required columns: 'BIW NUMBER', 'VEHICLE CODE', 'SHOP', 'PBS LIFT', 'HOLD BY', 'REASONS S', 'VIN'
    """
    if not isinstance(filepath_or_buffer, str):
        try:
            filepath_or_buffer.seek(0)
        except Exception:
            pass
    # Check if the file is an HTML table disguised as .xls (works for both
    # on-disk paths and in-memory uploads from st.file_uploader)
    is_html, html_content = _detect_html_content(filepath_or_buffer)

    if is_html:
        dfs = pd.read_html(io.StringIO(html_content))
        if not dfs:
            raise ValueError("No tables found in PPC Float Report HTML file.")
        df = dfs[0]
        # Promote first row to headers
        df.columns = [str(c).strip() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
    else:
        # Read the file using pd.read_excel
        if isinstance(filepath_or_buffer, str):
            ext = os.path.splitext(filepath_or_buffer.lower())[1]
            if ext == '.xlsb':
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            else:
                df = pd.read_excel(filepath_or_buffer)
        else:
            # For stream or bytes, let's try to detect/read
            try:
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            except Exception:
                try:
                    filepath_or_buffer.seek(0)
                    df = pd.read_excel(filepath_or_buffer)
                except Exception:
                    try:
                        filepath_or_buffer.seek(0)
                        dfs = pd.read_html(filepath_or_buffer)
                        df = dfs[0]
                        df.columns = [str(c).strip() for c in df.iloc[0]]
                        df = df.iloc[1:].reset_index(drop=True)
                    except Exception as e:
                        raise ValueError(f"Failed to load float report: {e}")

    df.columns = [str(c).strip() for c in df.columns]
    
    # Check columns
    req = ['BIW NUMBER', 'VEHICLE CODE', 'SHOP', 'PBS LIFT', 'HOLD BY', 'REASONS S', 'VIN']
    for r in req:
        if r not in df.columns:
            matched_col = [c for c in df.columns if r.lower() in c.lower() or (r == 'VEHICLE CODE' and c.lower() in ['vc', 'vehicle_code', 'vehicle code'])]
            if matched_col:
                df.rename(columns={matched_col[0]: r}, inplace=True)
                
    # Parse dates
    for date_col in ['BIW LIFTING', 'PTCED', 'SEALANT', 'TOPCOAT', 'PBS LIFT']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], format='mixed', dayfirst=True, errors='coerce')
            
    # Clean BIW NUMBER and VEHICLE CODE
    if 'BIW NUMBER' in df.columns:
        df['BIW NUMBER'] = df['BIW NUMBER'].apply(lambda x: str(int(x)) if pd.notna(x) and str(x).strip().replace('.0','').isdigit() else str(x).strip())
    if 'VEHICLE CODE' in df.columns:
        df['VEHICLE CODE'] = df['VEHICLE CODE'].astype(str).str.strip()
        df['VC'] = df['VEHICLE CODE']
    elif 'VC' in df.columns:
        df['VC'] = df['VC'].astype(str).str.strip()
        df['VEHICLE CODE'] = df['VC']
    else:
        df['VEHICLE CODE'] = ""
        df['VC'] = ""
    
    # Group by BIW NUMBER to aggregate multiple hold reasons
    # If a cab appears multiple times, it is because of multiple hold entries.
    # We combine 'HOLD BY' and 'REASONS S' by joining with a comma.
    def join_non_null(series):
        non_nulls = series.dropna().astype(str).str.strip()
        non_nulls = [n for n in non_nulls if n and n != 'nan']
        return ', '.join(dict.fromkeys(non_nulls)) # Deduplicated join
        
    def first_non_null(series):
        non_nulls = series.dropna()
        return non_nulls.iloc[0] if not non_nulls.empty else None
        
    agg_funcs = {}
    for col in df.columns:
        if col == 'BIW NUMBER':
            continue
        elif col in ['HOLD BY', 'REASONS S']:
            agg_funcs[col] = join_non_null
        else:
            agg_funcs[col] = first_non_null
            
    df_dedup = df.groupby('BIW NUMBER').agg(agg_funcs).reset_index()
    
    # Clean empty strings resulting from join_non_null back to None
    df_dedup['HOLD BY'] = df_dedup['HOLD BY'].replace('', None)
    df_dedup['REASONS S'] = df_dedup['REASONS S'].replace('', None)
    
    return df_dedup

def load_paint_summary_report(filepath_or_buffer):
    """
    Loads PPC Float Report Paint Summary (HTML or Excel format) and returns aggregated model stage totals.
    Uses dynamic header scanning and flexible row parsing to handle formatting variations across .xls and .xlsb files.
    """
    if not isinstance(filepath_or_buffer, str):
        try:
            filepath_or_buffer.seek(0)
        except Exception:
            pass
            
    is_html, html_content = _detect_html_content(filepath_or_buffer)

    if is_html:
        dfs = pd.read_html(io.StringIO(html_content))
        if not dfs:
            return {}
        df = dfs[0]
    else:
        if isinstance(filepath_or_buffer, str):
            ext = os.path.splitext(filepath_or_buffer.lower())[1]
            if ext == '.xlsb':
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            else:
                df = pd.read_excel(filepath_or_buffer)
        else:
            try:
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            except Exception:
                try:
                    filepath_or_buffer.seek(0)
                    df = pd.read_excel(filepath_or_buffer)
                except Exception:
                    try:
                        filepath_or_buffer.seek(0)
                        dfs = pd.read_html(filepath_or_buffer)
                        if not dfs:
                            return {}
                        df = dfs[0]
                    except Exception as e:
                        raise ValueError(f"Failed to load Paint Float Summary report: {e}")
                
    pf_map = {
        'HORNBILL': 'PUNCH',
        'NOVA': 'PUNCH.EV',
        'ETURNA': 'HARRIER.EV',
        'GRAVITAS': 'SAFARI',
        'Q5': 'HARRIER',
        'TAYRONA': 'SAFARI.EV'
    }
    
    stage_cols = [
        'TOTAL FLOAT', 'PBS FLOAT', 'PBS TO POLISHING', 'POLISHING TO TOPCOAT',
        'TOPCOAT TO WETSANDING G ROOFBLACK', 'TOPCOAT TO WETSANDING G FRESH',
        'WETSANDING G TO SEALANT', 'TOTAL UPTO SEALANT', 'PT ENTRY TO SEALANT',
        'BIW LIFTING G TO PT', 'PT BYPASS'
    ]
    
    col_map = {}
    header_row_idx = None
    for r_idx in range(min(10, len(df))):
        row_vals = [str(x).upper().strip() for x in df.iloc[r_idx].values]
        if any('TOTAL FLOAT' in x for x in row_vals):
            header_row_idx = r_idx
            for c_idx, val in enumerate(row_vals):
                if 'TOTAL FLOAT' in val and 'TOTAL FLOAT' not in col_map:
                    col_map['TOTAL FLOAT'] = c_idx
                elif 'PBS FLOAT' in val:
                    col_map['PBS FLOAT'] = c_idx
                elif 'PBS TO POLISHING' in val:
                    col_map['PBS TO POLISHING'] = c_idx
                elif 'POLISHING TO TOPCOAT' in val:
                    col_map['POLISHING TO TOPCOAT'] = c_idx
                elif 'TOPCOAT TO WETSANDING' in val or 'TOPCOAT TO WET' in val:
                    if 'ROOF' in val or 'BLACK' in val:
                        col_map['TOPCOAT TO WETSANDING G ROOFBLACK'] = c_idx
                    else:
                        col_map['TOPCOAT TO WETSANDING G FRESH'] = c_idx
                elif 'WETSANDING' in val and 'SEAL' in val:
                    col_map['WETSANDING G TO SEALANT'] = c_idx
                elif 'UPTO SEALANT' in val or 'UPTO SEALENT' in val:
                    col_map['TOTAL UPTO SEALANT'] = c_idx
                elif 'PT ENTRY' in val:
                    col_map['PT ENTRY TO SEALANT'] = c_idx
                elif 'BIW LIFTING' in val:
                    col_map['BIW LIFTING G TO PT'] = c_idx
                elif 'PT BYPASS' in val:
                    col_map['PT BYPASS'] = c_idx
            break
            
    # Fallback to default indices (5..15) if header parsing didn't map everything
    default_indices = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    for stage_name, default_idx in zip(stage_cols, default_indices):
        if stage_name not in col_map:
            col_map[stage_name] = default_idx
            
    model_totals = {m: {c: 0 for c in stage_cols} for m in ['PUNCH', 'PUNCH.EV', 'HARRIER.EV', 'SAFARI', 'HARRIER', 'SAFARI.EV']}
    
    start_r = (header_row_idx + 1) if header_row_idx is not None else 0
    for idx in range(start_r, len(df)):
        row = df.iloc[idx]
        cell_texts = [str(row.iloc[i]).strip() for i in range(min(4, len(row))) if pd.notna(row.iloc[i])]
        full_text = ' '.join(cell_texts).upper()
        
        for pf_name, model in pf_map.items():
            if pf_name in full_text and 'TOTAL' in full_text and 'GRAND' not in full_text and 'SUB' not in full_text:
                for stage_name in stage_cols:
                    c_idx = col_map[stage_name]
                    if c_idx < len(row):
                        try:
                            v_str = str(row.iloc[c_idx]).strip()
                            v = int(float(v_str)) if v_str and v_str.lower() != 'nan' else 0
                        except Exception:
                            v = 0
                        model_totals[model][stage_name] += v
                break

    return model_totals

def load_vgl(filepath_or_buffer):
    """
    Loads Vehicle Generation List / DPT Plan VIN Generation Report (.xls, .xlsx, .xlsb, HTML).
    Supports both old VGL format (cab-by-cab) and new DPT Plan format (VC-grouped VIN counts).
    """
    if not isinstance(filepath_or_buffer, str):
        try:
            filepath_or_buffer.seek(0)
        except Exception:
            pass

    is_html, html_content = _detect_html_content(filepath_or_buffer)

    pf_map = {
        'HORNBILL': 'PUNCH',
        'NOVA': 'PUNCH.EV',
        'ETURNA': 'HARRIER.EV',
        'GRAVITAS': 'SAFARI',
        'Q5': 'HARRIER',
        'TAYRONA': 'SAFARI.EV'
    }

    if is_html and html_content:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        rows = soup.find_all('tr')
        if rows:
            header = [td.get_text(strip=True) for td in rows[0].find_all(['td', 'th'])]
            header_str = ' '.join(header).upper()
            
            # Check if this is new DPT Plan VIN generation format (has MARKET and ProductFamily headers)
            if ('PRODUCTFAMILY' in header_str or 'PRODUCT FAMILY' in header_str or 'MARKET' in header_str) and 'SR NO' not in header_str:
                parsed_rows = []
                current_pf = ''
                for r in rows[1:]:
                    tds = [td.get_text(strip=True) for td in r.find_all(['td', 'th'])]
                    if len(tds) < 4:
                        continue
                    market, pf, vc, sales_desc = tds[0], tds[1], tds[2], tds[3]
                    vin_str = tds[5] if len(tds) > 5 else (tds[4] if len(tds) > 4 else '0')
                    
                    if pf:
                        current_pf = pf.strip().upper()
                        
                    if not vc or vc.upper() in ['TOTAL', 'GRAND TOTAL'] or market.upper() in ['TOTAL', 'GRAND TOTAL']:
                        continue
                        
                    try:
                        vin_cnt = int(float(str(vin_str).strip()))
                    except Exception:
                        vin_cnt = 0
                        
                    model = pf_map.get(current_pf, 'UNKNOWN')
                    if model == 'UNKNOWN':
                        for k, v in pf_map.items():
                            if k in sales_desc.upper() or k in current_pf:
                                model = v
                                break
                                
                    parsed_rows.append({
                        'VEHICLE CODE': str(vc).strip(),
                        'ProductFamily': current_pf,
                        'SALES DESCRIPTION': sales_desc,
                        'Model': model,
                        'Model_Family': model,
                        'VIN_Count': vin_cnt,
                        'CREATED DATE': pd.Timestamp.now()
                    })
                df_res = pd.DataFrame(parsed_rows)
                if not df_res.empty:
                    return df_res

    # Fallback reading via pd.read_html / pd.read_excel
    if is_html:
        dfs = pd.read_html(io.StringIO(html_content))
        df = dfs[0]
        df.columns = [str(c).strip() for c in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)
    else:
        if isinstance(filepath_or_buffer, str):
            ext = os.path.splitext(filepath_or_buffer.lower())[1]
            if ext == '.xlsb':
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            else:
                df = pd.read_excel(filepath_or_buffer)
        else:
            try:
                df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
            except Exception:
                try:
                    filepath_or_buffer.seek(0)
                    df = pd.read_excel(filepath_or_buffer)
                except Exception:
                    filepath_or_buffer.seek(0)
                    dfs = pd.read_html(filepath_or_buffer)
                    df = dfs[0]
                    df.columns = [str(c).strip() for c in df.iloc[0]]
                    df = df.iloc[1:].reset_index(drop=True)
        
    df.columns = [str(c).strip() for c in df.columns]

    standard_renames = {
        'VEHICLE CODE': 'VEHICLE CODE',
        'VC': 'VEHICLE CODE',
        'VEHICLE_CODE': 'VEHICLE CODE',
        'SHORT VEHICLE CODE': 'VEHICLE CODE',
        'FULL VC': 'VEHICLE CODE',
        'BIW NUMBER': 'BIW NUMBER',
        'VIN NUMBER': 'VIN NUMBER',
        'CREATED DATE': 'CREATED DATE',
        'SHIFT': 'SHIFT'
    }
    for col in list(df.columns):
        col_clean = str(col).strip()
        for std_key, std_val in standard_renames.items():
            if col_clean.lower() == std_key.lower():
                df.rename(columns={col: std_val}, inplace=True)
                break
                
    if 'VEHICLE CODE' in df.columns:
        df['VEHICLE CODE'] = df['VEHICLE CODE'].astype(str).str.strip()
        df['VC'] = df['VEHICLE CODE']
    else:
        df['VEHICLE CODE'] = ""
        df['VC'] = ""

    # Filter out total / summary rows
    vc_mask = df['VEHICLE CODE'].str.upper().isin(['TOTAL', 'GRAND TOTAL', 'NAN', ''])
    if 'MARKET' in df.columns:
        vc_mask = vc_mask | df['MARKET'].astype(str).str.strip().str.upper().isin(['TOTAL', 'GRAND TOTAL'])
    df = df[~vc_mask].reset_index(drop=True)

    if 'ProductFamily' in df.columns:
        df['ProductFamily'] = df['ProductFamily'].replace(r'^\s*$', None, regex=True).ffill()
    if 'PRODUCT' in df.columns:
        df['PRODUCT'] = df['PRODUCT'].replace(r'^\s*$', None, regex=True).ffill()

    vin_col = None
    for c in df.columns:
        c_str = str(c).strip().upper()
        if c_str in ['TCF/-VIN', 'TCF2-VIN', 'TCF-VIN', 'TCF1-VIN', 'TCF1_VIN', 'TCF2_VIN', 'VIN_COUNT', 'TODAY VIN', 'VIN GENERATION', 'VIN QTY', 'VIN_QTY']:
            vin_col = c
            break
        if 'VIN' in c_str and 'CODE' not in c_str and 'NUMBER' not in c_str and 'DESC' not in c_str and 'PLAN' not in c_str:
            vin_col = c
            break

    if vin_col:
        df['VIN_Count'] = pd.to_numeric(df[vin_col], errors='coerce').fillna(0).astype(int)
    else:
        df['VIN_Count'] = 1

    if 'BIW NUMBER' in df.columns:
        df['BIW NUMBER'] = df['BIW NUMBER'].apply(lambda x: str(int(float(x))) if pd.notna(x) and str(x).strip().replace('.0','').replace('e+','').replace('+','').isdigit() else str(x).strip())
    
    def map_model_family(row):
        pf = str(row.get('PRODUCT', row.get('ProductFamily', ''))).strip().upper()
        sd = str(row.get('SALES DESCRIPTION', row.get('SALES DESC', ''))).strip().upper()
        vc = str(row.get('VEHICLE CODE', row.get('VC', ''))).strip().upper()
        
        if 'NOVA' in pf or 'PUNCH.EV' in sd or 'PUNCH EV' in sd:
            return 'PUNCH.EV'
        elif 'HORNBILL' in pf or 'PUNCH' in sd:
            return 'PUNCH'
        elif 'ETURNA' in pf or 'HARRIER.EV' in sd or 'HARRIER EV' in sd:
            return 'HARRIER.EV'
        elif 'TAYRONA' in pf or 'SAFARI.EV' in sd or 'SAFARI EV' in sd or '54831927A' in vc:
            return 'SAFARI EV'
        elif 'GRAVITAS' in pf or 'SAFARI' in sd:
            return 'SAFARI'
        elif 'Q5' in pf or 'HARRIER' in sd:
            return 'HARRIER'
        for k, v in pf_map.items():
            if k in pf or k in sd:
                return v
        return 'UNKNOWN'
        
    df['Model_Family'] = df.apply(map_model_family, axis=1)
    df['Model'] = df['Model_Family']
    
    if 'CREATED DATE' in df.columns:
        df['CREATED DATE'] = pd.to_datetime(df['CREATED DATE'], dayfirst=True, errors='coerce')
        
    engine_col = None
    for col in df.columns:
        c_str = str(col).strip().lower()
        if 'engine part' in c_str or 'engine no' in c_str:
            engine_col = col
            break
            
    if engine_col:
        df.rename(columns={engine_col: 'RAW_ENGINE_PART'}, inplace=True)
    else:
        df['RAW_ENGINE_PART'] = None
        
    def extract_engine(val):
        if pd.isna(val):
            return None
        val_str = str(val).split('/')[0].strip()
        if val_str.lower() in ['na', 'none', '']:
            return None
        return val_str
        
    df['Engine_Part'] = df['RAW_ENGINE_PART'].apply(extract_engine)
    
    return df

def load_stock_grouped(filepath_or_buffer, sheet_name, vc_col_idx, part_col_idx, qty_col_idx, skip_rows=2):
    """
    Generic grouped-row stock parser.
    Skips skip_rows, reads columns by index, forward-fills part_number and qty,
    deduplicated to return a dict {part_number: qty}.
    """
    if not isinstance(filepath_or_buffer, str):
        try:
            filepath_or_buffer.seek(0)
        except Exception:
            pass
    # Read the sheet with no header to get index-based access
    # Detect file type
    if isinstance(filepath_or_buffer, str):
        ext = os.path.splitext(filepath_or_buffer.lower())[1]
        if ext == '.xlsb':
            df = pd.read_excel(filepath_or_buffer, sheet_name=sheet_name, engine='pyxlsb', header=None)
        else:
            df = pd.read_excel(filepath_or_buffer, sheet_name=sheet_name, engine='xlrd' if ext == '.xls' else 'openpyxl', header=None)
    else:
        # Uploaded bytes - let's check name if possible, otherwise try xlrd/openpyxl
        # We try to read it as excel
        try:
            df = pd.read_excel(filepath_or_buffer, sheet_name=sheet_name, engine='openpyxl', header=None)
        except Exception:
            try:
                # Seek back to 0
                filepath_or_buffer.seek(0)
                df = pd.read_excel(filepath_or_buffer, sheet_name=sheet_name, engine='xlrd', header=None)
            except Exception:
                filepath_or_buffer.seek(0)
                df = pd.read_excel(filepath_or_buffer, sheet_name=sheet_name, engine='pyxlsb', header=None)
                
    # Slice the data, skipping headers
    data = df.iloc[skip_rows:].copy()
    
    # Grab the target columns
    vc_col = data.iloc[:, vc_col_idx]
    part_col = data.iloc[:, part_col_idx]
    qty_col = data.iloc[:, qty_col_idx]
    
    # Clean part numbers and quantity
    parts_clean = part_col.apply(clean_part_number)
    
    # Build forward-filled list
    current_part = None
    current_qty = None
    
    part_to_qty = {}
    vc_to_part = {}
    
    for idx, (vc_val, part_val, qty_val) in enumerate(zip(vc_col, parts_clean, qty_col)):
        if part_val is not None:
            current_part = part_val
            # Clean qty value
            if pd.isna(qty_val) or str(qty_val).strip() == '':
                current_qty = 0
            else:
                try:
                    # If it is a string representing a float/int, parse it
                    qty_str = str(qty_val).strip()
                    if '.' in qty_str:
                        current_qty = int(float(qty_str))
                    else:
                        current_qty = int(qty_str)
                except ValueError:
                    current_qty = 0
                    
        if current_part is not None:
            part_to_qty[current_part] = current_qty
            
        if pd.notna(vc_val):
            vc_str = str(vc_val).strip()
            # Clean floats in VCs
            if vc_str.endswith('.0'):
                vc_str = vc_str[:-2]
            if len(vc_str) >= 8 and vc_str[0].isdigit():
                vc_to_part[vc_str] = current_part
                
    return part_to_qty, vc_to_part

def classify_files(uploaded_files):
    """
    Classifies a list of uploaded file wrappers by their filenames.
    Returns a dict mapping classification category to the file object.
    """
    classifications = {}
    
    for f in uploaded_files:
        name = f.name.lower()
        if 'bom' in name:
            classifications['BOM'] = f
        elif 'float' in name:
            if 'paint' in name:
                classifications['FLOAT_PAINT_SUMMARY'] = f
            else:
                classifications['FLOAT_REPORT'] = f
        elif any(k in name for k in ['vgl', 'vehicle_generation', 'generation_list', 'dpt-plan', 'dpt_plan', 'vin_generation', 'generation_report']):
            if 'tcf2' in name or 'tcf_2' in name:
                classifications['TCF2_VGL'] = f
            else:
                classifications['TCF1_VGL'] = f
        elif 'cockpit' in name:
            if 'tcf2' in name or 'tcf-2' in name or 'tcf_2' in name or 'harrier' in name or 'safari' in name:
                classifications['TCF2_COCKPIT_STOCK'] = f
            elif 'nova' in name:
                classifications['TCF1_NOVA_COCKPIT_STOCK'] = f
            else:
                classifications['TCF1_ALTROZ_COCKPIT_STOCK'] = f
        elif 'wiring' in name or 'harness' in name:
            if 'tcf2' in name or 'tcf-2' in name or 'tcf_2' in name:
                classifications['TCF2_WIRING_STOCK'] = f
            else:
                classifications['TCF1_WIRING_STOCK'] = f
                
    return classifications

def detect_and_classify_files(directory_path):
    """
    Scans directory_path (including subdirectories like 'Float reports/') and classifies all xls, xlsx, xlsb files by their names.
    Returns a dict mapping categories to their absolute file paths.
    """
    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        return {}
        
    classifications = {}
    file_entries = []
    
    try:
        # First scan files directly in directory_path
        for f in os.listdir(directory_path):
            p = os.path.join(directory_path, f)
            if os.path.isfile(p):
                file_entries.append((f, p))
                
        # Then scan subdirectories (e.g., Float reports, TEST)
        for f_dir in os.listdir(directory_path):
            p_dir = os.path.join(directory_path, f_dir)
            if os.path.isdir(p_dir) and not f_dir.startswith('.') and f_dir != '__pycache__':
                for root, dirs, files in os.walk(p_dir):
                    for f in files:
                        file_entries.append((f, os.path.join(root, f)))
    except Exception:
        return {}
        
    for name, path in file_entries:
        ext = os.path.splitext(name.lower())[1]
        if ext not in ['.xlsx', '.xls', '.xlsb', '.csv']:
            continue
            
        name_lower = name.lower()
        
        def set_cat(cat, p):
            if cat not in classifications:
                classifications[cat] = p
            else:
                existing = classifications[cat]
                # Prefer Float reports/ and root over TEST folder
                if 'test' in existing.lower() and 'test' not in p.lower():
                    classifications[cat] = p
                elif 'float reports' in p.lower() and 'float reports' not in existing.lower():
                    classifications[cat] = p

        if 'bom' in name_lower:
            set_cat('BOM', path)
        elif 'float' in name_lower:
            if 'paint' in name_lower:
                set_cat('FLOAT_PAINT_SUMMARY', path)
            else:
                set_cat('FLOAT_REPORT', path)
        elif any(k in name_lower for k in ['vgl', 'vehicle_generation', 'generation_list', 'dpt-plan', 'dpt_plan', 'vin_generation', 'generation_report']):
            if 'tcf2' in name_lower or 'tcf_2' in name_lower:
                set_cat('TCF2_VGL', path)
            else:
                set_cat('TCF1_VGL', path)
        elif 'cockpit' in name_lower:
            if 'tcf2' in name_lower or 'tcf-2' in name_lower or 'tcf_2' in name_lower or 'harrier' in name_lower or 'safari' in name_lower:
                set_cat('TCF2_COCKPIT_STOCK', path)
            elif 'nova' in name_lower:
                set_cat('TCF1_NOVA_COCKPIT_STOCK', path)
            else:
                set_cat('TCF1_ALTROZ_COCKPIT_STOCK', path)
        elif 'wiring' in name_lower or 'harness' in name_lower:
            if 'tcf2' in name_lower or 'tcf-2' in name_lower or 'tcf_2' in name_lower:
                set_cat('TCF2_WIRING_STOCK', path)
            else:
                set_cat('TCF1_WIRING_STOCK', path)
                
    return classifications

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clear_to_build.db")

def init_db():
    """Initializes the database and table if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bom_details (
            short_vehicle_code TEXT PRIMARY KEY,
            front_wiring TEXT,
            cockpit TEXT,
            engine TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_bom_to_db(df):
    """Overwrites the database table with the provided BOM DataFrame."""
    if df is None or df.empty:
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    # Convert dataframe to exactly match the database columns
    db_df = df.copy()
    db_df.columns = ['short_vehicle_code', 'front_wiring', 'cockpit', 'engine']
    db_df.to_sql('bom_details', conn, if_exists='replace', index=False)
    conn.commit()
    conn.close()

def load_bom_from_db():
    """Loads the BOM data from the database. Returns None if empty or table does not exist."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bom_details")
        count = cursor.fetchone()[0]
        if count == 0:
            return None
        df = pd.read_sql("SELECT * FROM bom_details", conn)
        # Rename back to the standard application columns
        df.rename(columns={
            'short_vehicle_code': 'Short Vehicle Code',
            'front_wiring': 'Front Wiring',
            'cockpit': 'Cockpit',
            'engine': 'Engine'
        }, inplace=True)
        return df
    except Exception:
        return None
    finally:
        conn.close()

def init_engine_db():
    """Initializes the engine stocks table if it does not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS engine_stocks (
            tcf_line TEXT,
            engine_part_no TEXT PRIMARY KEY,
            model TEXT,
            ta_code TEXT,
            clearance_qty INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_engine_stocks_to_db(df):
    """Saves the edited engine stocks DataFrame to the DB."""
    if df is None or df.empty:
        return
    init_engine_db()
    conn = sqlite3.connect(DB_PATH)
    db_df = df.copy()
    db_df.columns = ['tcf_line', 'engine_part_no', 'model', 'ta_code', 'clearance_qty']
    db_df.to_sql('engine_stocks', conn, if_exists='replace', index=False)
    conn.commit()
    conn.close()

def load_engine_stocks_from_db():
    """Loads engine stocks from the DB. Returns None if empty or table does not exist."""
    init_engine_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM engine_stocks")
        count = cursor.fetchone()[0]
        if count == 0:
            return None
        df = pd.read_sql("SELECT * FROM engine_stocks", conn)
        df.columns = ["TCF Line", "Engine Part No", "Model", "TA Code", "Clearance After 6:30AM"]
        return df
    except Exception:
        return None
    finally:
        conn.close()

def init_metadata_db():
    """Initializes the metadata table if it does not exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

def save_metadata(key, value):
    """Saves a metadata key-value pair to the database."""
    init_metadata_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def load_metadata(key, default=None):
    """Loads a metadata value by key from the database. Returns default if not found."""
    init_metadata_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return default
    except Exception:
        return default
    finally:
        conn.close()

def load_paint_summary_by_vc(filepath_or_buffer):
    """
    Loads PPC Float Report Paint Summary and returns stage float counts aggregated by Short Vehicle Code (SHORT VC).
    Returns dict: { '54734327A': {'TOTAL FLOAT': int, 'PBS FLOAT': int, 'TOTAL UPTO SEALANT': int}, ... }
    """
    if not filepath_or_buffer:
        return {}

    if not isinstance(filepath_or_buffer, str):
        try:
            filepath_or_buffer.seek(0)
        except Exception:
            pass
            
    is_html, html_content = _detect_html_content(filepath_or_buffer)

    try:
        if is_html:
            dfs = pd.read_html(io.StringIO(html_content))
            if not dfs:
                return {}
            df = dfs[0]
        else:
            if isinstance(filepath_or_buffer, str):
                ext = os.path.splitext(filepath_or_buffer.lower())[1]
                if ext == '.xlsb':
                    df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
                else:
                    df = pd.read_excel(filepath_or_buffer)
            else:
                try:
                    df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
                except Exception:
                    try:
                        filepath_or_buffer.seek(0)
                        df = pd.read_excel(filepath_or_buffer)
                    except Exception:
                        try:
                            filepath_or_buffer.seek(0)
                            dfs = pd.read_html(filepath_or_buffer)
                            if not dfs:
                                return {}
                            df = dfs[0]
                        except Exception:
                            return {}
    except Exception:
        return {}

    header_row_idx = None
    col_map = {}
    
    for r_idx in range(min(15, len(df))):
        row_vals = [str(x).upper().strip() for x in df.iloc[r_idx].values]
        if any('SHORT VC' in x or 'VEHICLE CODE' in x or x == 'VC' for x in row_vals) or any('TOTAL FLOAT' in x for x in row_vals):
            header_row_idx = r_idx
            for c_idx, val in enumerate(row_vals):
                if 'SHORT VC' in val or 'VEHICLE CODE' in val or val == 'VC':
                    col_map['VC'] = c_idx
                elif 'TOTAL FLOAT' in val and 'TOTAL FLOAT' not in col_map:
                    col_map['TOTAL FLOAT'] = c_idx
                elif 'PBS FLOAT' in val:
                    col_map['PBS FLOAT'] = c_idx
                elif 'UPTO SEALANT' in val or 'UPTO SEALENT' in val:
                    col_map['TOTAL UPTO SEALANT'] = c_idx
                elif 'PBS TO POLISHING' in val:
                    col_map['PBS TO POLISHING'] = c_idx
                elif 'POLISHING TO TOPCOAT' in val:
                    col_map['POLISHING TO TOPCOAT'] = c_idx
                elif 'TOPCOAT TO WETSANDING' in val or 'TOPCOAT TO WET' in val:
                    if 'ROOF' in val or 'BLACK' in val:
                        col_map['TOPCOAT TO WETSANDING G ROOFBLACK'] = c_idx
                    else:
                        col_map['TOPCOAT TO WETSANDING G FRESH'] = c_idx
                elif 'WETSANDING' in val and 'SEAL' in val:
                    col_map['WETSANDING G TO SEALANT'] = c_idx
            break

    vc_counts = {}
    if header_row_idx is not None and 'VC' in col_map:
        vc_cidx = col_map['VC']
        tot_cidx = col_map.get('TOTAL FLOAT')
        pbs_cidx = col_map.get('PBS FLOAT')
        seal_cidx = col_map.get('TOTAL UPTO SEALANT')
        
        start_r = header_row_idx + 1
        for idx in range(start_r, len(df)):
            row = df.iloc[idx]
            if vc_cidx < len(row):
                raw_vc = str(row.iloc[vc_cidx]).strip()
                if raw_vc and raw_vc.lower() != 'nan' and len(raw_vc) >= 8 and not raw_vc.upper().startswith('TOTAL'):
                    svc = raw_vc[:9]
                    
                    def get_int(c_idx):
                        if c_idx is not None and c_idx < len(row):
                            try:
                                v_str = str(row.iloc[c_idx]).strip()
                                return int(float(v_str)) if v_str and v_str.lower() != 'nan' else 0
                            except Exception:
                                return 0
                        return 0
                        
                    tot = get_int(tot_cidx)
                    pbs = get_int(pbs_cidx)
                    
                    if seal_cidx is not None:
                        seal = get_int(seal_cidx)
                    else:
                        seal = pbs + get_int(col_map.get('PBS TO POLISHING')) + get_int(col_map.get('POLISHING TO TOPCOAT')) + get_int(col_map.get('TOPCOAT TO WETSANDING G ROOFBLACK')) + get_int(col_map.get('TOPCOAT TO WETSANDING G FRESH')) + get_int(col_map.get('WETSANDING G TO SEALANT'))
                        
                    if svc not in vc_counts:
                        vc_counts[svc] = {'TOTAL FLOAT': 0, 'PBS FLOAT': 0, 'TOTAL UPTO SEALANT': 0}
                    vc_counts[svc]['TOTAL FLOAT'] += tot
                    vc_counts[svc]['PBS FLOAT'] += pbs
                    vc_counts[svc]['TOTAL UPTO SEALANT'] += seal
                    
    return vc_counts
