import pandas as pd
import numpy as np
import io
import re
import os
import openpyxl
import pyxlsb

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

def load_bom(filepath_or_buffer):
    """
    Loads BOM details.xlsx and returns a cleaned DataFrame.
    Expected columns: 'Short Vehicle Code', 'Front Wiring', 'Cockpit ', 'Engine'
    """
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
    Loads PPC Float Report (.xlsb) and returns a cleaned DataFrame.
    Required columns: 'BIW NUMBER', 'VEHICLE CODE', 'SHOP', 'PBS LIFT', 'HOLD BY', 'REASONS S', 'VIN'
    """
    # Read the file using pyxlsb
    if isinstance(filepath_or_buffer, str):
        df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
    else:
        # Streamlit uploaded file (BytesIO)
        df = pd.read_excel(filepath_or_buffer, engine='pyxlsb')
        
    df.columns = [str(c).strip() for c in df.columns]
    
    # Check columns
    req = ['BIW NUMBER', 'VEHICLE CODE', 'SHOP', 'PBS LIFT', 'HOLD BY', 'REASONS S', 'VIN']
    for r in req:
        if r not in df.columns:
            matched_col = [c for c in df.columns if r.lower() in c.lower()]
            if matched_col:
                df.rename(columns={matched_col[0]: r}, inplace=True)
                
    # Parse dates
    for date_col in ['BIW LIFTING', 'PTCED', 'SEALANT', 'TOPCOAT', 'PBS LIFT']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
            
    # Clean BIW NUMBER and VEHICLE CODE
    df['BIW NUMBER'] = df['BIW NUMBER'].apply(lambda x: str(int(x)) if pd.notna(x) and str(x).strip().replace('.0','').isdigit() else str(x).strip())
    df['VEHICLE CODE'] = df['VEHICLE CODE'].astype(str).str.strip()
    
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

def load_vgl(filepath_or_buffer):
    """
    Loads Vehicle Generation List (.xls) which is actually HTML.
    Expected columns: 'VEHICLE CODE', 'BIW NUMBER', 'VIN NUMBER', 'CREATED DATE', 'SHIFT',
    and either 'ENGINE PART NO / ALTERNATE PART NO' or 'ENGINE PART NO'.
    """
    # Read HTML
    if isinstance(filepath_or_buffer, str):
        dfs = pd.read_html(filepath_or_buffer)
    else:
        # BytesIO
        dfs = pd.read_html(filepath_or_buffer)
        
    if not dfs:
        raise ValueError("No tables found in Vehicle Generation List file.")
        
    df = dfs[0]
    # Promote first row to headers if it has header labels
    df.columns = [str(c).strip() for c in df.iloc[0]]
    df = df.iloc[1:].reset_index(drop=True)
    
    # Rename columns to standard names
    standard_renames = {
        'VEHICLE CODE': 'VEHICLE CODE',
        'BIW NUMBER': 'BIW NUMBER',
        'VIN NUMBER': 'VIN NUMBER',
        'CREATED DATE': 'CREATED DATE',
        'SHIFT': 'SHIFT'
    }
    for col in df.columns:
        col_clean = str(col).strip()
        for std_key, std_val in standard_renames.items():
            if col_clean.lower() == std_key.lower():
                df.rename(columns={col: std_val}, inplace=True)
                
    # Find engine column
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
        
    # Clean VEHICLE CODE and BIW NUMBER
    df['VEHICLE CODE'] = df['VEHICLE CODE'].astype(str).str.strip()
    df['BIW NUMBER'] = df['BIW NUMBER'].apply(lambda x: str(int(float(x))) if pd.notna(x) and str(x).strip().replace('.0','').replace('e+','').replace('+','').isdigit() else str(x).strip())
    
    # Parse date
    if 'CREATED DATE' in df.columns:
        df['CREATED DATE'] = pd.to_datetime(df['CREATED DATE'], dayfirst=True, errors='coerce')
        
    # Extract primary engine part number (split by ' / ' if present)
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
            classifications['FLOAT_REPORT'] = f
        elif 'vgl' in name or 'vehicle_generation' in name or 'generation_list' in name:
            if 'tcf2' in name or 'tcf_2' in name:
                classifications['TCF2_VGL'] = f
            else:
                classifications['TCF1_VGL'] = f
        elif 'wiring' in name or 'harness' in name:
            if 'tcf2' in name or 'tcf-2' in name or 'tcf_2' in name:
                classifications['TCF2_WIRING_STOCK'] = f
            else:
                classifications['TCF1_WIRING_STOCK'] = f
        elif 'cockpit' in name:
            if 'tcf2' in name or 'tcf-2' in name or 'tcf_2' in name:
                classifications['TCF2_COCKPIT_STOCK'] = f
            elif 'nova' in name:
                classifications['TCF1_NOVA_COCKPIT_STOCK'] = f
            else:
                classifications['TCF1_ALTROZ_COCKPIT_STOCK'] = f
                
    return classifications
