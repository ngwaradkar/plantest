import os
import sys
import shutil
import config

def run_pipeline():
    print("Starting Data Pipeline Orchestrator...")
    original_path = config.EXCEL_PATH
    ext = ".xlsm" if original_path.endswith(".xlsm") else ".xlsx"
    staging_path = original_path.replace(ext, f"_Staging{ext}")
    
    # 1. Copy the current workbook to staging to avoid Excel file lock (PermissionError)
    print(f"Creating staging copy at: {staging_path}")
    shutil.copy(original_path, staging_path)
    
    # 2. Redirect config to staging
    config.EXCEL_PATH = staging_path
    
    # 3. Run the phases sequentially
    import refresh_data
    import excel_allocation_engine
    import excel_paint_tcf_float
    import logger
    import time
    
    logger.init_log()
    
    try:
        print("Running Phase 2 (Data Ingestion)...")
        t0 = time.time()
        refresh_data.run_refresh()
        logger.log_event("Data Ingestion", "refresh_data", "Success", "Phase 2 completed", "", round(time.time()-t0, 2))
    except Exception as e:
        logger.log_event("Data Ingestion", "refresh_data", "Critical", "Phase 2 failed", str(e))
        
    try:
        print("Running Phase 3 (Stock Calculation)...")
        t0 = time.time()
        excel_allocation_engine.run_phase3()
        logger.log_event("Stock Calculation", "excel_allocation_engine", "Success", "Phase 3 completed", "", round(time.time()-t0, 2))
    except Exception as e:
        logger.log_event("Stock Calculation", "excel_allocation_engine", "Critical", "Phase 3 failed", str(e))
        
    try:
        print("Running Phase 5 (Paint & TCF Float Summaries)...")
        t0 = time.time()
        excel_paint_tcf_float.run_phase5()
        logger.log_event("Float Summaries", "excel_paint_tcf_float", "Success", "Phase 5 completed", "", round(time.time()-t0, 2))
    except Exception as e:
        logger.log_event("Float Summaries", "excel_paint_tcf_float", "Error", "Phase 5 failed", str(e))
        
    print("Pipeline execution complete! Staging file is ready for Excel to ingest.")

if __name__ == "__main__":
    run_pipeline()
