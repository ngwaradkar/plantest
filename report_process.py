"""
process.py - Core processing logic for TML Paint Aging Report
Reads PPC Float Report (XLSB/XLSX) and generates Paint & WBS Ageing Analysis Excel.
"""

import os
import re
import tempfile
import datetime
from io import BytesIO
from typing import List, Set

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ─────────────────────────────────────────────
#  Helpers & Date extraction
# ─────────────────────────────────────────────
def extract_date_from_filename(filename: str) -> datetime.date | None:
    if not filename:
        return None
    # Matches dd_mm_yyyy or d_m_yyyy or dd-mm-yyyy etc.
    match = re.search(r"(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})", filename)
    if match:
        d, m, y = map(int, match.groups())
        try:
            return datetime.date(y, m, d)
        except ValueError:
            try:
                return datetime.date(y, d, m)
            except ValueError:
                pass
    return None


# ─────────────────────────────────────────────
#  Product code → display name mapping
#  TAYRONA (Safari EV) excluded – single car,
#  project under development
# ─────────────────────────────────────────────
PRODUCT_MAP = {
    "HORNBILL": "Punch",
    "NOVA":     "Nova",
    "ETURNA":   "Harrier EV",
    "Q5":       "Harrier",
    "GRAVITAS": "Safari",
    # TAYRONA → excluded
}

MODEL_ORDER = ["Punch", "Nova", "Harrier", "Safari", "Harrier EV"]

BUCKET_ORDER = [
    "More than 15 days",
    "11 to 15 Days",
    "8 to 10 Days",
    "4 To 7 Days",
    "2 to 3 Days",
    "1 Day",
]

# Excel colour codes for aging buckets (green → red gradient)
BUCKET_FILLS = {
    "1 Day":              "E2EFDA",
    "2 to 3 Days":        "FFF2CC",
    "4 To 7 Days":        "FCE4D6",
    "8 to 10 Days":       "F4CCCC",
    "11 to 15 Days":      "EA9999",
    "More than 15 days":  "C00000",
}

BUCKET_FONT_WHITE = {"More than 15 days", "11 to 15 Days"}


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _parse_dt(val) -> datetime.datetime | None:
    """Parse a datetime from string or existing datetime object."""
    if val is None:
        return None
    if isinstance(val, (datetime.datetime, pd.Timestamp)):
        if pd.isna(val):
            return None
        return val.to_pydatetime() if hasattr(val, 'to_pydatetime') else val
    s = str(val).strip()
    if s in ("None", "", "nan", "NaN", "NaT"):
        return None
    for fmt in ("%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        ts = pd.to_datetime(s, format="mixed", dayfirst=True)
        if pd.notna(ts):
            return ts.to_pydatetime()
    except Exception:
        pass
    return None


def _aging_days(
    event_dt: datetime.datetime | None,
    analysis_date: datetime.date,
    holiday_dates: Set[datetime.date],
) -> int:
    """
    Calendar days from event_dt date to analysis_date,
    minus any holidays that fall strictly between the two dates.
    Returns 0 if same day or event is in the future.
    """
    if event_dt is None:
        return 0
    event_d = event_dt.date()
    if event_d >= analysis_date:
        return 0                        # same day or future → exclude
    total = (analysis_date - event_d).days
    holidays_between = sum(1 for h in holiday_dates if event_d < h < analysis_date)
    return max(0, total - holidays_between)


def _bucket_label(days: int) -> str | None:
    if days <= 0:
        return None
    if days == 1:
        return "1 Day"
    if days <= 3:
        return "2 to 3 Days"
    if days <= 7:
        return "4 To 7 Days"
    if days <= 10:
        return "8 to 10 Days"
    if days <= 15:
        return "11 to 15 Days"
    return "More than 15 days"


# ─────────────────────────────────────────────
#  File reading
# ─────────────────────────────────────────────

def _read_xlsb(file_bytes: bytes) -> pd.DataFrame:
    from pyxlsb import open_workbook
    with tempfile.NamedTemporaryFile(suffix=".xlsb", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        with open_workbook(tmp_path) as wb:
            sname = wb.sheets[0]
            with wb.get_sheet(sname) as sheet:
                rows = [[cell.v for cell in row] for row in sheet.rows()]
    finally:
        os.unlink(tmp_path)

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("Uploaded XLSB file appears to be empty.")
    # Strip whitespace from column names (pyxlsb can return trailing spaces)
    df.columns = [str(c).strip() if c is not None else "" for c in df.iloc[0]]
    df = df.iloc[1:].reset_index(drop=True)
    return df


def _read_xlsx(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), header=0)
    # Strip whitespace from column names for consistency
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _read_html(file_bytes: bytes) -> pd.DataFrame:
    dfs = pd.read_html(BytesIO(file_bytes), header=0)
    if not dfs:
        raise ValueError("No HTML table found in file.")
    df = dfs[0]
    df.columns = [str(c).strip() if c is not None else "" for c in df.columns]
    return df


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(BytesIO(file_bytes), header=0, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(BytesIO(file_bytes), header=0, encoding="cp1252")
    # If the CSV parser returned a single column containing HTML tags, it's HTML not CSV
    if len(df.columns) == 1 and any(tag in str(df.columns[0]).lower() for tag in ["<html", "<table", "<style"]):
        raise ValueError("File contains HTML markup, not CSV.")
    # Strip whitespace from column names for consistency
    df.columns = [str(c).strip() for c in df.columns]
    return df


def read_float_report(file_bytes: bytes, filename: str) -> pd.DataFrame:
    fn_lower = filename.lower()
    
    # Try reading based on extension first, then fallback to others
    if fn_lower.endswith(".xlsb"):
        readers = [_read_xlsb, _read_xlsx, _read_html, _read_csv]
    elif fn_lower.endswith(".csv"):
        readers = [_read_csv, _read_html, _read_xlsx, _read_xlsb]
    elif fn_lower.endswith((".xlsx", ".xls", ".html", ".htm")):
        readers = [_read_xlsx, _read_html, _read_xlsb, _read_csv]
    else:
        readers = [_read_xlsb, _read_xlsx, _read_html, _read_csv]

    for reader in readers:
        try:
            df = reader(file_bytes)
            # Ensure it returned a valid dataframe with multiple columns
            if isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 1:
                return df
        except Exception:
            pass

    raise ValueError(
        "Could not automatically detect the file format. Please ensure you are uploading "
        "a valid raw PPC Float Report (XLSB, XLSX, XLS, HTML, or CSV)."
    )


# ─────────────────────────────────────────────
#  Main processing entry point
# ─────────────────────────────────────────────

def process_aging(
    file_bytes: bytes,
    filename: str,
    analysis_date: datetime.date,
    holidays: List[datetime.date],
) -> tuple:
    """
    Generate aging report from PPC Float Report.

    Returns
    -------
    excel_bytes : bytes
        The generated Excel workbook as bytes.
    df_biw : pd.DataFrame
        Detail records for BIW to PT analysis.
    df_pt : pd.DataFrame
        Detail records for PT to PBS analysis.
    summary_biw : dict
        Pivot counts for BIW to PT summary.
    summary_pt : dict
        Pivot counts for PT to PBS summary.
    """
    holiday_dates: Set[datetime.date] = set()
    for h in holidays:
        if isinstance(h, datetime.datetime):
            holiday_dates.add(h.date())
        elif isinstance(h, datetime.date):
            holiday_dates.add(h)

    df = read_float_report(file_bytes, filename)

    # ── Normalise column names: strip all whitespace ──
    df.columns = [str(c).strip() for c in df.columns]

    # Build normalized lookup to find columns case/space/underscore/hyphen-insensitively
    def normalize_str(s: str) -> str:
        return s.replace(" ", "").replace("_", "").replace("-", "").upper()

    col_normalized = {normalize_str(c): c for c in df.columns}

    def _col(name: str, optional: bool = False) -> str | None:
        """Find the actual column name regardless of whitespace/case/delimiters."""
        if name in df.columns:
            return name
        norm_name = normalize_str(name)
        if norm_name in col_normalized:
            return col_normalized[norm_name]
        
        # Check aliases
        aliases = {
            "COLOUR": ["COLOR", "PAINTCOLOUR", "PAINTCOLOR", "COLOURDESC", "COLORDESC"],
            "VEHICLECODE": ["VC", "SHORTVEHICLECODE", "VEHICLE_CODE"],
            "SALESDESCRIPTION": ["SALESDESC", "DESCRIPTION", "VARIANT", "MODELDESCRIPTION"],
            "REASONSS": ["REASONS", "REASON", "HOLDREASON", "HOLDREASONS"],
            "HOLDBY": ["HOLD_BY", "HOLD", "HELD_BY", "HOLDBYAGENCY"],
            "SHOP": ["LINE", "SHOPLINE"],
        }
        for alias in aliases.get(norm_name, []):
            if alias in col_normalized:
                return col_normalized[alias]

        if optional:
            return None

        # Check if they uploaded an output/summary template file
        cols_str = str(list(df.columns))
        if "Unnamed: 0" in cols_str or ("SR NO" in cols_str and "Ageing" in cols_str):
            raise ValueError(
                f"Required column '{name}' is missing. It looks like you uploaded the "
                f"**Paint and WBS Ageing analysis** output report/template by mistake instead of the "
                f"raw **PPC Float Report**! Please upload the raw Float Report (containing columns "
                f"like BIW LIFTING, PTCED, PBS LIFT, PRODUCT, etc.)."
            )
        else:
            raise ValueError(
                f"Required column '{name}' was not found in the uploaded file. "
                f"Available columns: {list(df.columns)}. "
                f"Please ensure you are uploading the correct PPC Float Report."
            )

    biw_col     = _col("BIW LIFTING")
    ptced_col   = _col("PTCED")
    pbs_col     = _col("PBS LIFT")
    prod_col    = _col("PRODUCT")
    biw_num_col = _col("BIW NUMBER")
    vin_col     = _col("VIN", optional=True)
    vcode_col   = _col("VEHICLE CODE", optional=True)
    desc_col    = _col("SALES DESCRIPTION", optional=True)
    colour_col  = _col("COLOUR", optional=True)
    hold_col    = _col("HOLD BY", optional=True)
    shop_col    = _col("SHOP", optional=True)

    if vin_col is None:
        df["VIN"] = ""
        vin_col = "VIN"
    if vcode_col is None:
        df["VEHICLE CODE"] = ""
        vcode_col = "VEHICLE CODE"
    if desc_col is None:
        df["SALES DESCRIPTION"] = ""
        desc_col = "SALES DESCRIPTION"
    if colour_col is None:
        df["COLOUR"] = ""
        colour_col = "COLOUR"
    if shop_col is None:
        df["SHOP"] = ""
        shop_col = "SHOP"

    # Parse timestamp columns
    df["BIW_DT"]  = df[biw_col].apply(_parse_dt)
    df["PTCED_DT"] = df[ptced_col].apply(_parse_dt)
    df["PBS_DT"]   = df[pbs_col].apply(_parse_dt)

    # Apply product mapping; TAYRONA rows drop out (map returns NaN)
    df["MODEL_NAME"] = df[prod_col].map(PRODUCT_MAP)
    df_valid = df[df["MODEL_NAME"].notna()].copy()

    # ── BIW to PT: BIW LIFTING filled, PTCED empty ──
    df_biw = df_valid[
        df_valid["BIW_DT"].notna() & df_valid["PTCED_DT"].isna()
    ].copy()
    df_biw = df_biw.drop_duplicates(subset=[biw_num_col], keep="first")
    df_biw["aging_days"] = df_biw["BIW_DT"].apply(
        lambda x: _aging_days(x, analysis_date, holiday_dates)
    )
    df_biw = df_biw[df_biw["aging_days"] > 0].copy()   # exclude same-day
    df_biw["Ageing"] = df_biw["aging_days"].apply(_bucket_label)
    df_biw = df_biw.sort_values("BIW_DT").reset_index(drop=True)
    df_biw["SR NO"] = range(1, len(df_biw) + 1)

    # ── PT to PBS: PTCED filled, PBS LIFT empty ──
    df_pt = df_valid[
        df_valid["PTCED_DT"].notna() & df_valid["PBS_DT"].isna()
    ].copy()
    df_pt = df_pt.drop_duplicates(subset=[biw_num_col], keep="first")
    df_pt["aging_days"] = df_pt["PTCED_DT"].apply(
        lambda x: _aging_days(x, analysis_date, holiday_dates)
    )
    df_pt = df_pt[df_pt["aging_days"] > 0].copy()      # exclude same-day
    df_pt["Ageing"] = df_pt["aging_days"].apply(_bucket_label)
    df_pt = df_pt.sort_values("PTCED_DT").reset_index(drop=True)
    df_pt["SR NO"] = range(1, len(df_pt) + 1)

    # ── PBS Aging: PBS LIFT filled ──
    df_pbs_raw = df_valid[df_valid["PBS_DT"].notna()].copy()
    df_pbs_raw["aging_days"] = df_pbs_raw["PBS_DT"].apply(
        lambda x: _aging_days(x, analysis_date, holiday_dates)
    )
    df_pbs_raw = df_pbs_raw[df_pbs_raw["aging_days"] > 0].copy()   # exclude same-day
    df_pbs_raw["Ageing"] = df_pbs_raw["aging_days"].apply(_bucket_label)

    # Resolve new columns
    df_pbs_raw["VIN"] = df_pbs_raw[vin_col]
    df_pbs_raw["VEHICLE CODE"] = df_pbs_raw[vcode_col]
    df_pbs_raw["SALES DESCRIPTION"] = df_pbs_raw[desc_col]
    if hold_col and hold_col in df_pbs_raw.columns:
        df_pbs_raw["HOLD BY"] = df_pbs_raw[hold_col]
    else:
        df_pbs_raw["HOLD BY"] = ""

    # Group by BIW NUMBER to aggregate reasons case-insensitively and keep vehicle counts unique
    agg_dict = {
        "MODEL_NAME": "first",
        "COLOUR": "first",
        "SHOP": "first",
        "PBS_DT": "first",
        "PBS LIFT": "first",
        "aging_days": "first",
        "Ageing": "first",
        "VIN": "first",
        "VEHICLE CODE": "first",
        "SALES DESCRIPTION": "first",
        "HOLD BY": "first",
    }
    
    reasons_col = None
    try:
        reasons_col = _col("REASONS S")
    except Exception:
        pass

    if reasons_col and reasons_col in df_pbs_raw.columns:
        def join_reasons(series):
            seen = set()
            unique_reasons = []
            for val in series.dropna():
                s_val = str(val).strip()
                if s_val and s_val.lower() not in ("none", "", "nan"):
                     if s_val.lower() not in seen:
                         seen.add(s_val.lower())
                         unique_reasons.append(s_val)
            return "; ".join(unique_reasons) if unique_reasons else ""
        
        df_pbs_raw["Reason_for_aging"] = df_pbs_raw[reasons_col]
        agg_dict["Reason_for_aging"] = join_reasons
    else:
        df_pbs_raw["Reason_for_aging"] = ""
        agg_dict["Reason_for_aging"] = "first"

    df_pbs = df_pbs_raw.groupby(biw_num_col, as_index=False).agg(agg_dict)
    
    # Ensure BIW NUMBER column name matches original lookup in final DataFrame
    df_pbs["BIW NUMBER"] = df_pbs[biw_num_col]
    df_pbs = df_pbs.sort_values("PBS_DT").reset_index(drop=True)
    df_pbs["SR NO"] = range(1, len(df_pbs) + 1)

    summary_biw = _pivot(df_biw)
    summary_pt  = _pivot(df_pt)
    summary_pbs = _pivot(df_pbs)

    # Prepare Hold Cabs Report
    df_hold_cabs = get_hold_cabs_report(
        df_valid, biw_num_col, vin_col, vcode_col, prod_col, desc_col, hold_col, reasons_col, pbs_col, colour_col, ptced_col, analysis_date, holiday_dates
    )

    excel_bytes = _build_excel(df_biw, df_pt, df_hold_cabs, analysis_date)
    pbs_excel_bytes = _build_pbs_excel(df_pbs, analysis_date)
    hold_excel_bytes = _build_hold_excel(df_hold_cabs)

    return excel_bytes, df_biw, df_pt, summary_biw, summary_pt, pbs_excel_bytes, df_pbs, summary_pbs, hold_excel_bytes, df_hold_cabs


def process_aging_from_df(
    df_input: pd.DataFrame,
    analysis_date: datetime.date,
    holidays: List[datetime.date],
) -> tuple:
    """
    Generate aging report from an already-loaded DataFrame.
    Serializes the DataFrame to CSV internally and delegates to process_aging().
    Used by the Planner Dashboard integration to avoid separate file upload.

    Parameters & Returns: same as process_aging().
    """
    buf = BytesIO()
    df_input.to_csv(buf, index=False)
    return process_aging(buf.getvalue(), "dashboard_float.csv", analysis_date, holidays)


# ─────────────────────────────────────────────
#  Summary pivot helper
# ─────────────────────────────────────────────

def _pivot(df: pd.DataFrame) -> dict:
    """Returns {model: {bucket: count, 'Total': count}} for all models."""
    result = {}
    for model in MODEL_ORDER:
        sub = df[df["MODEL_NAME"] == model]
        row = {b: int((sub["Ageing"] == b).sum()) for b in BUCKET_ORDER}
        row["Total"] = len(sub)
        result[model] = row
    return result


# ─────────────────────────────────────────────
#  Excel building
# ─────────────────────────────────────────────

def _build_excel(
    df_biw: pd.DataFrame,
    df_pt:  pd.DataFrame,
    df_hold: pd.DataFrame,
    analysis_date: datetime.date,
) -> bytes:
    wb = Workbook()

    _fill_summary(wb.active, df_biw, df_pt)
    wb.active.title = "Summary"

    ws_biw = wb.create_sheet("BIW to PT")
    _fill_detail(ws_biw, df_biw, "BIW LIFTING")

    ws_pt = wb.create_sheet("PT to PBS")
    _fill_detail(ws_pt, df_pt, "PTCED")

    ws_paint = wb.create_sheet("Paint shop Hold Cabs")
    df_paint = df_hold[df_hold["Agency"] == "Paint shop"].copy()
    df_paint["SR NO"] = range(1, len(df_paint) + 1)
    _fill_hold_cab_detail(ws_paint, df_paint)

    ws_biw_cabs = wb.create_sheet("BIW Hold Cabs")
    df_biw_cabs = df_hold[df_hold["Agency"].isin(["Punch BIW", "NOVA BIW"])].copy()
    df_biw_cabs["SR NO"] = range(1, len(df_biw_cabs) + 1)
    _fill_hold_cab_detail(ws_biw_cabs, df_biw_cabs)

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _styles() -> dict:
    """Return a shared dict of openpyxl style objects."""
    def fill(hex_color):
        return PatternFill("solid", fgColor=hex_color)

    def border():
        thin = Side(style="thin", color="B8CCE4")
        return Border(left=thin, right=thin, top=thin, bottom=thin)

    return dict(
        # fills
        f_header=fill("1F4E79"),
        f_model0=fill("DEEAF1"),
        f_model1=fill("EBF3FB"),
        f_total =fill("BDD7EE"),
        f_white =fill("FFFFFF"),
        f_jblock=fill("F2F8FC"),
        # bucket fills built lazily
        f_bucket={k: fill(v) for k, v in BUCKET_FILLS.items()},
        # fonts
        fnt_hdr  =Font(name="Calibri", bold=True, color="FFFFFF",  size=11),
        fnt_title=Font(name="Calibri", bold=True, color="1F4E79",  size=12),
        fnt_total=Font(name="Calibri", bold=True,                   size=10),
        fnt_body =Font(name="Calibri",                              size=10),
        fnt_white=Font(name="Calibri", bold=True, color="FFFFFF",  size=10),
        # alignment
        center=Alignment(horizontal="center", vertical="center"),
        left  =Alignment(horizontal="left",   vertical="center"),
        # border
        bdr=border(),
    )


def _fill_summary(ws, df_biw, df_pt):
    s = _styles()

    for i, w in enumerate([5, 26, 20, 15, 15, 13, 13, 10, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    def write_section(df, start_row, section_title, lift_label):
        r = start_row
        ws.row_dimensions[r].height = 18

        # Section title
        ws.merge_cells(f"B{r}:I{r}")
        c = ws.cell(r, 2, section_title)
        c.font = s["fnt_title"]
        c.alignment = s["left"]
        r += 2

        # Column headers
        ws.row_dimensions[r].height = 22
        headers = ["Model"] + BUCKET_ORDER + ["Total"]
        for ci, h in enumerate(headers, 2):
            c = ws.cell(r, ci, h)
            c.fill = s["f_header"]
            c.font = s["fnt_hdr"]
            c.alignment = s["center"]
            c.border = s["bdr"]
        r += 1

        # Model rows
        pivot = _pivot(df)
        for mi, model in enumerate(MODEL_ORDER):
            ws.row_dimensions[r].height = 18
            row_data = pivot[model]
            fill = s["f_model0"] if mi % 2 == 0 else s["f_model1"]

            c = ws.cell(r, 2, model)
            c.fill = fill; c.font = s["fnt_body"]; c.alignment = s["left"]; c.border = s["bdr"]

            for ci, bucket in enumerate(BUCKET_ORDER, 3):
                val = row_data[bucket]
                c = ws.cell(r, ci, val if val else None)
                c.fill = fill; c.font = s["fnt_body"]; c.alignment = s["center"]; c.border = s["bdr"]

            total = row_data["Total"]
            c = ws.cell(r, 9, total if total else None)
            c.fill = fill; c.font = s["fnt_total"]; c.alignment = s["center"]; c.border = s["bdr"]
            r += 1

        # Total lift row
        ws.row_dimensions[r].height = 20
        c = ws.cell(r, 2, lift_label)
        c.fill = s["f_total"]; c.font = s["fnt_total"]; c.alignment = s["left"]; c.border = s["bdr"]

        for ci, bucket in enumerate(BUCKET_ORDER, 3):
            val = sum(pivot[m][bucket] for m in MODEL_ORDER)
            c = ws.cell(r, ci, val)
            c.fill = s["f_total"]; c.font = s["fnt_total"]; c.alignment = s["center"]; c.border = s["bdr"]

        c = ws.cell(r, 9, len(df))
        c.fill = s["f_total"]; c.font = s["fnt_total"]; c.alignment = s["center"]; c.border = s["bdr"]
        r += 1

        # J Block row  (tracked separately – zero unless J-Block shop data present)
        ws.row_dimensions[r].height = 18
        j_fill = s["f_jblock"]
        c = ws.cell(r, 2, "J Block")
        c.fill = j_fill; c.font = s["fnt_body"]; c.alignment = s["left"]; c.border = s["bdr"]
        for ci in range(3, 9):
            c = ws.cell(r, ci, None)
            c.fill = j_fill; c.border = s["bdr"]; c.font = s["fnt_body"]; c.alignment = s["center"]
        c = ws.cell(r, 9, 0)
        c.fill = j_fill; c.font = s["fnt_body"]; c.alignment = s["center"]; c.border = s["bdr"]
        r += 1
        return r

    row = 2
    row = write_section(df_biw, row, "BIW to PT- Age Analysis",  "BIW to PT Lift")
    row += 1    # blank
    write_section(df_pt, row, "PT to PBS- Age Analysis", "PT to PBS Lift")


def _fill_detail(ws, df: pd.DataFrame, date_col: str):
    s = _styles()

    col_widths = [8, 15, 16, 14, 8, 26, 18]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Header row
    ws.row_dimensions[1].height = 22
    headers = ["SR NO", "BIW NUMBER", "PRODUCT", "COLOUR", "SHOP", date_col, "Ageing"]
    for ci, h in enumerate(headers, 1):
        c = ws.cell(1, ci, h)
        c.fill = s["f_header"]
        c.font = s["fnt_hdr"]
        c.alignment = s["center"]
        c.border = s["bdr"]

    # Data rows
    for ri, (_, row) in enumerate(df.iterrows(), 2):
        ws.row_dimensions[ri].height = 16
        is_alt = (ri % 2 == 0)
        row_fill = s["f_model1"] if is_alt else s["f_white"]

        ageing = row.get("Ageing", "")
        bucket_fill = s["f_bucket"].get(ageing, s["f_white"])
        bucket_font = s["fnt_white"] if ageing in BUCKET_FONT_WHITE else s["fnt_body"]

        vals = [
            int(row.get("SR NO", ri - 1)),
            row.get("BIW NUMBER", ""),
            row.get("MODEL_NAME", ""),
            row.get("COLOUR", ""),
            row.get("SHOP", ""),
            row.get(date_col, row.get(date_col.strip(), "")),
            ageing,
        ]

        for ci, val in enumerate(vals, 1):
            c = ws.cell(ri, ci)
            c.value = val if val is not None else ""
            if ci == 7:          # Ageing column – colour coded
                c.fill = bucket_fill
                c.font = bucket_font
            else:
                c.fill = row_fill
                c.font = s["fnt_body"]
            c.alignment = s["left"] if ci == 2 else s["center"]
            c.border = s["bdr"]


# ─────────────────────────────────────────────
#  PBS Excel Building
# ─────────────────────────────────────────────

def _build_pbs_excel(
    df_pbs: pd.DataFrame,
    analysis_date: datetime.date,
) -> bytes:
    wb = Workbook()

    _fill_pbs_summary(wb.active, df_pbs)
    wb.active.title = "Summary"

    ws_detail = wb.create_sheet("PBS Detail")
    _fill_pbs_detail(ws_detail, df_pbs)

    ws_hold = wb.create_sheet("Cabs >2 Days")
    df_hold = df_pbs[df_pbs["aging_days"] > 2].copy().reset_index(drop=True)
    df_hold["SR NO"] = range(1, len(df_hold) + 1)
    _fill_pbs_hold_detail(ws_hold, df_hold)

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _fill_pbs_summary(ws, df_pbs):
    s = _styles()

    for i, w in enumerate([5, 26, 20, 15, 15, 13, 13, 10, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    def write_section(df, start_row, section_title, lift_label):
        r = start_row
        ws.row_dimensions[r].height = 18

        # Section title
        ws.merge_cells(f"B{r}:I{r}")
        c = ws.cell(r, 2, section_title)
        c.font = s["fnt_title"]
        c.alignment = s["left"]
        r += 2

        # Column headers
        ws.row_dimensions[r].height = 22
        headers = ["Model"] + BUCKET_ORDER + ["Total"]
        for ci, h in enumerate(headers, 2):
            c = ws.cell(r, ci, h)
            c.fill = s["f_header"]
            c.font = s["fnt_hdr"]
            c.alignment = s["center"]
            c.border = s["bdr"]
        r += 1

        # Model rows
        pivot = _pivot(df)
        for mi, model in enumerate(MODEL_ORDER):
            ws.row_dimensions[r].height = 18
            row_data = pivot[model]
            fill = s["f_model0"] if mi % 2 == 0 else s["f_model1"]

            c = ws.cell(r, 2, model)
            c.fill = fill; c.font = s["fnt_body"]; c.alignment = s["left"]; c.border = s["bdr"]

            for ci, bucket in enumerate(BUCKET_ORDER, 3):
                val = row_data[bucket]
                c = ws.cell(r, ci, val if val else None)
                c.fill = fill; c.font = s["fnt_body"]; c.alignment = s["center"]; c.border = s["bdr"]

            total = row_data["Total"]
            c = ws.cell(r, 9, total if total else None)
            c.fill = fill; c.font = s["fnt_total"]; c.alignment = s["center"]; c.border = s["bdr"]
            r += 1

        # Total lift row
        ws.row_dimensions[r].height = 20
        c = ws.cell(r, 2, lift_label)
        c.fill = s["f_total"]; c.font = s["fnt_total"]; c.alignment = s["left"]; c.border = s["bdr"]

        for ci, bucket in enumerate(BUCKET_ORDER, 3):
            val = sum(pivot[m][bucket] for m in MODEL_ORDER)
            c = ws.cell(r, ci, val)
            c.fill = s["f_total"]; c.font = s["fnt_total"]; c.alignment = s["center"]; c.border = s["bdr"]

        c = ws.cell(r, 9, len(df))
        c.fill = s["f_total"]; c.font = s["fnt_total"]; c.alignment = s["center"]; c.border = s["bdr"]
        r += 1

        # J Block row
        ws.row_dimensions[r].height = 18
        j_fill = s["f_jblock"]
        c = ws.cell(r, 2, "J Block")
        c.fill = j_fill; c.font = s["fnt_body"]; c.alignment = s["left"]; c.border = s["bdr"]
        for ci in range(3, 9):
            c = ws.cell(r, ci, None)
            c.fill = j_fill; c.border = s["bdr"]; c.font = s["fnt_body"]; c.alignment = s["center"]
        c = ws.cell(r, 9, 0)
        c.fill = j_fill; c.font = s["fnt_body"]; c.alignment = s["center"]; c.border = s["bdr"]
        r += 1
        return r

    write_section(df_pbs, 2, "PBS - Age Analysis", "PBS Lift")


def _fill_pbs_detail(ws, df: pd.DataFrame):
    s = _styles()

    col_widths = [8, 20, 15, 18, 16, 28, 14, 8, 26, 16, 18]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Header row
    ws.row_dimensions[1].height = 22
    headers = ["SR NO", "VIN", "BIW NUMBER", "VEHICLE CODE", "PRODUCT", "SALES DESCRIPTION", "COLOUR", "SHOP", "PBS LIFT", "HOLD BY", "Ageing"]
    for ci, h in enumerate(headers, 1):
        c = ws.cell(1, ci, h)
        c.fill = s["f_header"]
        c.font = s["fnt_hdr"]
        c.alignment = s["center"]
        c.border = s["bdr"]

    # Data rows
    for ri, (_, row) in enumerate(df.iterrows(), 2):
        ws.row_dimensions[ri].height = 16
        is_alt = (ri % 2 == 0)
        row_fill = s["f_model1"] if is_alt else s["f_white"]

        ageing = row.get("Ageing", "")
        bucket_fill = s["f_bucket"].get(ageing, s["f_white"])
        bucket_font = s["fnt_white"] if ageing in BUCKET_FONT_WHITE else s["fnt_body"]

        vals = [
            int(row.get("SR NO", ri - 1)),
            row.get("VIN", ""),
            row.get("BIW NUMBER", ""),
            row.get("VEHICLE CODE", ""),
            row.get("MODEL_NAME", ""),
            row.get("SALES DESCRIPTION", ""),
            row.get("COLOUR", ""),
            row.get("SHOP", ""),
            row.get("PBS LIFT", ""),
            row.get("HOLD BY", ""),
            ageing,
        ]

        for ci, val in enumerate(vals, 1):
            c = ws.cell(ri, ci)
            c.value = val if val is not None else ""
            if ci == 11:          # Ageing column – colour coded
                c.fill = bucket_fill
                c.font = bucket_font
            else:
                c.fill = row_fill
                c.font = s["fnt_body"]
            c.alignment = s["left"] if ci in (2, 3, 4, 6, 10) else s["center"]
            c.border = s["bdr"]


def _fill_pbs_hold_detail(ws, df: pd.DataFrame):
    s = _styles()

    col_widths = [8, 20, 15, 18, 16, 28, 14, 8, 26, 16, 10, 18, 45]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Header row
    ws.row_dimensions[1].height = 22
    headers = ["SR NO", "VIN", "BIW NUMBER", "VEHICLE CODE", "PRODUCT", "SALES DESCRIPTION", "COLOUR", "SHOP", "PBS LIFT", "HOLD BY", "Days", "Ageing", "Reason for aging"]
    for ci, h in enumerate(headers, 1):
        c = ws.cell(1, ci, h)
        c.fill = s["f_header"]
        c.font = s["fnt_hdr"]
        c.alignment = s["center"]
        c.border = s["bdr"]

    # Data rows
    for ri, (_, row) in enumerate(df.iterrows(), 2):
        ws.row_dimensions[ri].height = 16
        is_alt = (ri % 2 == 0)
        row_fill = s["f_model1"] if is_alt else s["f_white"]

        ageing = row.get("Ageing", "")
        bucket_fill = s["f_bucket"].get(ageing, s["f_white"])
        bucket_font = s["fnt_white"] if ageing in BUCKET_FONT_WHITE else s["fnt_body"]

        vals = [
            int(row.get("SR NO", ri - 1)),
            row.get("VIN", ""),
            row.get("BIW NUMBER", ""),
            row.get("VEHICLE CODE", ""),
            row.get("MODEL_NAME", ""),
            row.get("SALES DESCRIPTION", ""),
            row.get("COLOUR", ""),
            row.get("SHOP", ""),
            row.get("PBS LIFT", ""),
            row.get("HOLD BY", ""),
            row.get("aging_days", 0),
            ageing,
            row.get("Reason_for_aging", ""),
        ]

        for ci, val in enumerate(vals, 1):
            c = ws.cell(ri, ci)
            c.value = val if val is not None else ""
            if ci == 12:          # Ageing column – colour coded
                c.fill = bucket_fill
                c.font = bucket_font
            else:
                c.fill = row_fill
                c.font = s["fnt_body"]
            c.alignment = s["left"] if ci in (2, 3, 4, 6, 10, 13) else s["center"]
            c.border = s["bdr"]


def get_hold_cabs_report(df_valid, biw_num_col, vin_col, vcode_col, prod_col, desc_col, hold_col, reasons_col, pbs_col, colour_col, ptced_col, analysis_date, holiday_dates) -> pd.DataFrame:
    # 1. Filter: PTCED is not null
    df_ptced = df_valid[df_valid["PTCED_DT"].notna()].copy()
    
    # 2. Filter: HOLD BY is not null/empty/None
    if hold_col and hold_col in df_ptced.columns:
        df_hold = df_ptced[
            df_ptced[hold_col].notna() & 
            (df_ptced[hold_col].astype(str).str.strip().str.lower() != "none") & 
            (df_ptced[hold_col].astype(str).str.strip() != "")
        ].copy()
    else:
        return pd.DataFrame(columns=["SR NO", "VIN", "BIW NUMBER", "VEHICLE CODE", "PRODUCT", "COLOUR", "PTCED", "PBS LIFT", "Days", "HOLD BY", "Reason", "Location", "Agency"])

    # 3. Resolve columns
    df_hold["VIN"] = df_hold[vin_col]
    df_hold["BIW NUMBER"] = df_hold[biw_num_col]
    df_hold["VEHICLE CODE"] = df_hold[vcode_col]
    df_hold["PRODUCT"] = df_hold["MODEL_NAME"]
    df_hold["COLOUR"] = df_hold[colour_col] if colour_col else ""
    df_hold["HOLD BY"] = df_hold[hold_col]
    df_hold["PTCED"] = df_hold[ptced_col].fillna("")
    df_hold["PBS LIFT"] = df_hold[pbs_col].fillna("")

    # Resolve location: if PBS LIFT is not null -> pbs, else -> paintshop
    df_hold["Location"] = df_hold["PBS_DT"].apply(
        lambda x: "pbs" if pd.notna(x) else "paintshop"
    )

    # Calculate Days (aging days)
    def calc_days(row):
        loc = row["Location"]
        if loc == "pbs":
            dt = row["PBS_DT"]
        else:
            dt = row["PTCED_DT"]
        return _aging_days(dt, analysis_date, holiday_dates) if pd.notna(dt) else 0

    df_hold["Days"] = df_hold.apply(calc_days, axis=1)

    # Resolve agency
    def _map_agency(val):
        if pd.isna(val):
            return ""
        s_val = str(val).strip().lower()
        if s_val == "129505":
            return "Paint shop"
        elif s_val == "dss293693":
            return "Punch BIW"
        elif s_val == "q1":
            return "NOVA BIW"
        return str(val).strip()

    df_hold["Agency"] = df_hold["HOLD BY"].apply(_map_agency)

    # 4. Group by BIW NUMBER to aggregate Reasons and keep unique rows
    agg_dict = {
        "VIN": "first",
        "VEHICLE CODE": "first",
        "PRODUCT": "first",
        "COLOUR": "first",
        "HOLD BY": "first",
        "Location": "first",
        "Agency": "first",
        "PTCED_DT": "first",
        "PTCED": "first",
        "PBS LIFT": "first",
        "Days": "first",
    }

    if reasons_col and reasons_col in df_hold.columns:
        def join_reasons(series):
            seen = set()
            unique_reasons = []
            for val in series.dropna():
                s_val = str(val).strip()
                if s_val and s_val.lower() not in ("none", "", "nan"):
                     if s_val.lower() not in seen:
                         seen.add(s_val.lower())
                         unique_reasons.append(s_val)
            return "; ".join(unique_reasons) if unique_reasons else ""
        
        df_hold["Reason"] = df_hold[reasons_col]
        agg_dict["Reason"] = join_reasons
    else:
        df_hold["Reason"] = ""
        agg_dict["Reason"] = "first"

    df_grouped = df_hold.groupby("BIW NUMBER", as_index=False).agg(agg_dict)
    
    # Sort by PTCED_DT
    df_grouped = df_grouped.sort_values("PTCED_DT").reset_index(drop=True)
    df_grouped["SR NO"] = range(1, len(df_grouped) + 1)
    
    return df_grouped


def _build_hold_excel(df_hold: pd.DataFrame) -> bytes:
    wb = Workbook()
    
    # 1. Summary sheet
    ws_sum = wb.active
    ws_sum.title = "Summary"
    _fill_hold_summary(ws_sum, df_hold)
    
    # 2. Paint shop Cabs sheet
    ws_paint = wb.create_sheet("Paint shop Cabs")
    df_paint = df_hold[df_hold["Agency"] == "Paint shop"].copy()
    df_paint["SR NO"] = range(1, len(df_paint) + 1)
    _fill_hold_cab_detail(ws_paint, df_paint)
    
    # 3. BIW Cabs sheet
    ws_biw = wb.create_sheet("BIW Cabs")
    df_biw_cabs = df_hold[df_hold["Agency"].isin(["Punch BIW", "NOVA BIW"])].copy()
    df_biw_cabs["SR NO"] = range(1, len(df_biw_cabs) + 1)
    _fill_hold_cab_detail(ws_biw, df_biw_cabs)
    
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _fill_hold_summary(ws, df: pd.DataFrame):
    s = _styles()
    
    # Column widths
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["E"].width = 25
    ws.column_dimensions["F"].width = 15
    
    # Title Block for Table 1
    ws.merge_cells("B2:C2")
    ws["B2"] = "Product wise Hold Cabs"
    ws["B2"].font = s["fnt_hdr"]
    ws["B2"].fill = s["f_header"]
    ws["B2"].alignment = s["center"]
    
    # Headers Table 1
    ws["B3"] = "Product"
    ws["B3"].font = s["fnt_hdr"]
    ws["B3"].fill = s["f_header"]
    ws["B3"].border = s["bdr"]
    ws["B3"].alignment = s["left"]
    
    ws["C3"] = "Count"
    ws["C3"].font = s["fnt_hdr"]
    ws["C3"].fill = s["f_header"]
    ws["C3"].border = s["bdr"]
    ws["C3"].alignment = s["center"]
    
    # Write Product counts
    products = ["Punch", "Nova", "Harrier", "Safari", "Harrier EV"]
    r = 4
    for p in products:
        c_prod = df[df["PRODUCT"] == p]
        count = len(c_prod)
        
        c = ws.cell(r, 2, p)
        c.font = s["fnt_body"]
        c.border = s["bdr"]
        c.alignment = s["left"]
        
        c2 = ws.cell(r, 3, count if count else None)
        c2.font = s["fnt_body"]
        c2.border = s["bdr"]
        c2.alignment = s["center"]
        r += 1
        
    # Total product row
    c = ws.cell(r, 2, "Total")
    c.font = s["fnt_total"]
    c.fill = s["f_total"]
    c.border = s["bdr"]
    c.alignment = s["left"]
    
    c2 = ws.cell(r, 3, len(df))
    c2.font = s["fnt_total"]
    c2.fill = s["f_total"]
    c2.border = s["bdr"]
    c2.alignment = s["center"]
    
    # Title Block for Table 2
    ws.merge_cells("E2:F2")
    ws["E2"] = "Agency wise Hold Cabs"
    ws["E2"].font = s["fnt_hdr"]
    ws["E2"].fill = s["f_header"]
    ws["E2"].alignment = s["center"]
    
    # Headers Table 2
    ws["E3"] = "Agency"
    ws["E3"].font = s["fnt_hdr"]
    ws["E3"].fill = s["f_header"]
    ws["E3"].border = s["bdr"]
    ws["E3"].alignment = s["left"]
    
    ws["F3"] = "Count"
    ws["F3"].font = s["fnt_hdr"]
    ws["F3"].fill = s["f_header"]
    ws["F3"].border = s["bdr"]
    ws["F3"].alignment = s["center"]
    
    agencies = ["Paint shop", "Punch BIW", "NOVA BIW"]
    r_ag = 4
    for ag in agencies:
        c_ag = df[df["Agency"] == ag]
        count = len(c_ag)
        
        c = ws.cell(r_ag, 5, ag)
        c.font = s["fnt_body"]
        c.border = s["bdr"]
        c.alignment = s["left"]
        
        c2 = ws.cell(r_ag, 6, count if count else None)
        c2.font = s["fnt_body"]
        c2.border = s["bdr"]
        c2.alignment = s["center"]
        r_ag += 1
        
    # Check for any other agencies
    other_cabs = df[~df["Agency"].isin(agencies)]
    if len(other_cabs) > 0:
        c = ws.cell(r_ag, 5, "Other")
        c.font = s["fnt_body"]
        c.border = s["bdr"]
        c.alignment = s["left"]
        
        c2 = ws.cell(r_ag, 6, len(other_cabs))
        c2.font = s["fnt_body"]
        c2.border = s["bdr"]
        c2.alignment = s["center"]
        r_ag += 1
        
    # Total agency row
    c = ws.cell(r_ag, 5, "Total")
    c.font = s["fnt_total"]
    c.fill = s["f_total"]
    c.border = s["bdr"]
    c.alignment = s["left"]
    
    c2 = ws.cell(r_ag, 6, len(df))
    c2.font = s["fnt_total"]
    c2.fill = s["f_total"]
    c2.border = s["bdr"]
    c2.alignment = s["center"]


def _fill_hold_cab_detail(ws, df: pd.DataFrame):
    s = _styles()

    col_widths = [8, 20, 15, 18, 16, 14, 26, 26, 10, 16, 45, 16, 16]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Header row
    ws.row_dimensions[1].height = 22
    headers = ["SR NO", "VIN", "BIW NO", "VEHICLE CODE", "PRODUCT", "COLOUR", "PTCED", "PBS LIFT", "Days", "HOLD BY", "Reason", "Location", "Agency"]
    for ci, h in enumerate(headers, 1):
        c = ws.cell(1, ci, h)
        c.fill = s["f_header"]
        c.font = s["fnt_hdr"]
        c.alignment = s["center"]
        c.border = s["bdr"]

    # Data rows
    for ri, (_, row) in enumerate(df.iterrows(), 2):
        ws.row_dimensions[ri].height = 16
        is_alt = (ri % 2 == 0)
        row_fill = s["f_model1"] if is_alt else s["f_white"]

        vals = [
            int(row.get("SR NO", ri - 1)),
            row.get("VIN", ""),
            row.get("BIW NUMBER", ""),
            row.get("VEHICLE CODE", ""),
            row.get("PRODUCT", ""),
            row.get("COLOUR", ""),
            row.get("PTCED", ""),
            row.get("PBS LIFT", ""),
            row.get("Days", 0),
            row.get("HOLD BY", ""),
            row.get("Reason", ""),
            row.get("Location", ""),
            row.get("Agency", ""),
        ]

        for ci, val in enumerate(vals, 1):
            c = ws.cell(ri, ci)
            c.value = val if val is not None else ""
            c.fill = row_fill
            c.font = s["fnt_body"]
            c.alignment = s["left"] if ci in (2, 3, 4, 11, 13) else s["center"]
            c.border = s["bdr"]

