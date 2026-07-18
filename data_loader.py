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
    Loads PPC Float Report (which can be .xlsb or .xls disguised HTML) and returns a cleaned DataFrame.
    Required columns: 'BIW NUMBER', 'VEHICLE CODE', 'SHOP', 'PBS LIFT', 'HOLD BY', 'REASONS S', 'VIN'
    """
    # Check if the file is an HTML table disguised as .xls
    is_html = False
    if isinstance(filepath_or_buffer, str):
        ext = os.path.splitext(filepath_or_buffer.lower())[1]
        if ext == '.xls':
            try:
                with open(filepath_or_buffer, 'r', encoding='utf-8', errors='ignore') as f:
                    first_chars = f.read(500)
                    if '<html' in first_chars.lower() or '<style' in first_chars.lower() or '<table' in first_chars.lower():
                        is_html = True
            except Exception:
                pass
                
    if is_html:
        dfs = pd.read_html(filepath_or_buffer)
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
    Scans directory_path and classifies all xls, xlsx, xlsb files by their names.
    Returns a dict mapping categories to their absolute file paths.
    """
    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        return {}
        
    classifications = {}
    
    # List files in directory
    try:
        filenames = os.listdir(directory_path)
    except Exception:
        return {}
        
    for name in filenames:
        path = os.path.join(directory_path, name)
        if not os.path.isfile(path):
            continue
            
        ext = os.path.splitext(name.lower())[1]
        if ext not in ['.xlsx', '.xls', '.xlsb', '.csv']:
            continue
            
        name_lower = name.lower()
        
        if 'bom' in name_lower:
            classifications['BOM'] = path
        elif 'float' in name_lower:
            classifications['FLOAT_REPORT'] = path
        elif 'vgl' in name_lower or 'vehicle_generation' in name_lower or 'generation_list' in name_lower:
            if 'tcf2' in name_lower or 'tcf_2' in name_lower:
                classifications['TCF2_VGL'] = path
            else:
                classifications['TCF1_VGL'] = path
        elif 'cockpit' in name_lower:
            if 'tcf2' in name_lower or 'tcf-2' in name_lower or 'tcf_2' in name_lower or 'harrier' in name_lower or 'safari' in name_lower:
                classifications['TCF2_COCKPIT_STOCK'] = path
            elif 'nova' in name_lower:
                classifications['TCF1_NOVA_COCKPIT_STOCK'] = path
            else:
                classifications['TCF1_ALTROZ_COCKPIT_STOCK'] = path
        elif 'wiring' in name_lower or 'harness' in name_lower:
            if 'tcf2' in name_lower or 'tcf-2' in name_lower or 'tcf_2' in name_lower:
                classifications['TCF2_WIRING_STOCK'] = path
            else:
                classifications['TCF1_WIRING_STOCK'] = path
                
    return classifications

DB_PATH = r"d:\Planner Dashboard\clear_to_build.db"

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
