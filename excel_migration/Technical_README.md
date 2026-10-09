# TCF Dashboard: Technical README

This document outlines the underlying architecture of `TCF Dashboard.xlsm`, built to fully decouple the original Streamlit application from Python and run 100% natively in Excel.

## 1. Architecture Overview

The workbook is split into three decoupled layers:
1. **Data Ingestion (Power Query)**: Extracts, transforms, and loads (ETL) data from local and OneDrive files into hidden raw tables (`_RawFloat`, `_RawVGL1`, etc.).
2. **Allocation Engine (VBA)**: Contains the heavy business logic (`AllocationEngine.bas`). It parses the BOM and Stock, builds a virtual inventory using high-speed `Scripting.Dictionary` objects, loops through the FIFO queue, and allocates BIWs.
3. **Presentation (Excel Formulas)**: The Dashboard uses `COUNTIF`, `SUMIFS`, and dynamic arrays to present the results calculated by the VBA engine.

## 2. Power Query Setup & The HTML-XLS Quirks

The original Streamlit application had special handling for `.xls` files downloaded from the SAP/corporate portal, which were actually **HTML tables disguised as XLS files**.

**How to handle this in Power Query:**
If you try to import these files normally using `Excel.Workbook`, Power Query will throw a `DataFormat.Error`. Instead, use the Web Page parser on the local file!

Example M-Code for `_RawFloat`:
```powerquery
let
    // 1. Get file path from the Settings Excel table
    SourcePath = Excel.CurrentWorkbook(){[Name="tblSettings"]}[Content]{0}[Value],
    
    // 2. Read the local file as HTML (NOT Excel!)
    Source = Web.Page(File.Contents(SourcePath & "\PPC_Float_Report.xls")),
    
    // 3. Extract the first table
    Data = Source{0}[Data]
in
    Data
```
Use this exact pattern for the Paint Summary and VGL reports.

## 3. VBA Modules

### `AllocationEngine.bas`
This is the core FIFO engine ported directly from `allocation_engine.py`. 
- It uses 2D Variant Arrays to read the Excel tables instantly.
- It uses Memory Dictionaries (`CreateObject("Scripting.Dictionary")`) for O(1) stock lookup.
- It writes the entire `df_alloc` array back to `tblFIFOAllocation` in a single operation to avoid cell-by-cell write lag.

### `AutoRefresh.bas`
Handles the orchestration:
1. Calls `ThisWorkbook.RefreshAll` to trigger Power Query.
2. Waits for completion (`BackgroundQuery = False`).
3. Triggers `RunAllocation`.
4. Updates the timestamps and `Log` sheet.

### `ThisWorkbook.cls`
Hooks into the Workbook open/close events to start and stop the `Application.OnTime` timer, preventing runaway background refresh loops.

## 4. How to Change Paths or Add New Reports

**Changing Paths:**
Do not hardcode paths in Power Query. Always reference the `tblSettings` table located on the `Settings` sheet. 
To change a path, the user simply edits the cell in `Settings`.

**Adding New Reports:**
1. Drop the new report in the folder.
2. Go to **Data > Get Data > Power Query Editor**.
3. Create a new Blank Query, use `Web.Page(File.Contents(...))` if it's an SAP HTML export, or `Excel.Workbook` if it's a true Excel file.
4. Close & Load To... a new hidden sheet (e.g., `_RawNewReport`).
5. Modify `AllocationEngine.bas` to pull the new table into an array if the FIFO logic requires it.

## 5. Security and Sheet Protection

- The `Validation` sheet and `_Raw*` sheets should be hidden (`xlSheetVeryHidden` via VBA) before final distribution to prevent user tampering.
- The `Dashboard` sheet can be protected (Review > Protect Sheet) with objects/charts unlocked to allow slicers to work, while protecting the KPI formulas.
- Do not password-protect the VBA project unless required by IT, to ensure future maintainability.
