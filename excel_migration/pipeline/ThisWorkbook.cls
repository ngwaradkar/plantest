VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "ThisWorkbook"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Option Explicit

Private Sub Workbook_Open()
    ' Initialize the dashboard UI and start timer if Auto-Refresh is ON
    Call ScheduleNextRefresh
End Sub

Private Sub Workbook_BeforeClose(Cancel As Boolean)
    ' Crucial: Stop the timer before closing to prevent Excel from reopening automatically
    Call StopTimer
End Sub
