# TCF Dashboard: User Setup Guide

Welcome to the TCF Dashboard. This Excel application requires absolutely zero installations—no Python, no Streamlit, no development environment. It runs entirely on native Microsoft Excel, Power Query, and VBA.

## Normal Daily Workflow

1. **Open the Workbook**: Open `TCF Dashboard.xlsm`.
2. **Enable Content**: If Excel displays a yellow banner at the top saying "Macros have been disabled" or "Data Connections have been disabled", click **Enable Content**.
3. **Start Auto-Refresh**: 
   - By default, the dashboard will attempt to auto-refresh every 5 minutes if enabled in Settings.
   - You can pause this at any time by going to the `Settings` sheet and changing `Auto Refresh Enabled` to `OFF`.
4. **Manual Refresh**: 
   - You can force an immediate update at any time by clicking the **REFRESH DASHBOARD** button on the main Dashboard sheet.
   - The timestamp for *Last Refresh* will update when finished.

## First-Time Configuration

If this is your first time opening the dashboard on a new PC, you need to point it to your local files.

1. Navigate to the **Settings** worksheet.
2. Locate the **System Configurations** section.
3. Update the folder paths to match your PC. For example, change `D:\Dashboard Files` to your actual OneDrive sync folder or local path.
4. Go to **Data > Get Data > Power Query Editor** (or just click **Refresh All**). If prompted for Privacy Levels, select "Ignore" or "Organization".

## Troubleshooting

- **#REF! or 0s on Dashboard**: This usually means a source file is missing. Check the **Log** sheet to see if the Data Refresh step reported a missing file.
- **Refresh button doesn't do anything**: Ensure Macros are enabled in Excel Trust Center.
- **Data doesn't look updated**: Check the *Next Refresh* time. If you just dropped a new file into the OneDrive folder, it may take a few minutes for the timer to pick it up, or you can click *Refresh Dashboard* manually.
