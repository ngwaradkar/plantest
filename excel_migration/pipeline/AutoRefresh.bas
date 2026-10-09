Attribute VB_Name = "AutoRefresh"
Option Explicit

Public RunTime As Double
Public IsRefreshing As Boolean

' -------------------------------------------------------------------------
' Main Entry Point: Refresh Dashboard
' -------------------------------------------------------------------------
Public Sub RefreshDashboard()
    If IsRefreshing Then Exit Sub
    IsRefreshing = True
    
    Dim wsLog As Worksheet, wsDash As Worksheet, wsSettings As Worksheet
    Set wsLog = ThisWorkbook.Sheets("Log")
    Set wsDash = ThisWorkbook.Sheets("Dashboard")
    Set wsSettings = ThisWorkbook.Sheets("Settings")
    
    On Error GoTo ErrorHandler
    
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    ' 1. Refresh Power Query connections and wait
    LogMessage "Info", "Refreshing Power Query connections..."
    Dim conn As WorkbookConnection
    For Each conn In ThisWorkbook.Connections
        If conn.Type = xlConnectionTypeOLEDB Then
            conn.OLEDBConnection.BackgroundQuery = False
        End If
        If conn.Type = xlConnectionTypeODBC Then
            conn.ODBCConnection.BackgroundQuery = False
        End If
        conn.Refresh
    Next conn
    
    ' 2. Calculate aggregations
    Application.Calculation = xlCalculationAutomatic
    Application.Calculate
    DoEvents
    
    ' 3. Run FIFO Allocation Engine (Phase 4 VBA)
    RunAllocation
    
    ' 4. Update Timestamps and Dashboard Status
    wsDash.Range("K3").Value = "✅ ONLINE"
    wsDash.Range("K3").Font.Color = RGB(0, 176, 80)
    
    wsDash.Range("H3").Value = Format(Now, "dd-mmm-yyyy hh:mm AM/PM")
    Dim nextRef As Date
    nextRef = DateAdd("n", GetRefreshInterval(), Now)
    wsDash.Range("H4").Value = Format(nextRef, "dd-mmm-yyyy hh:mm AM/PM")
    
    LogMessage "Success", "Dashboard refreshed successfully"
    
    IsRefreshing = False
    Application.ScreenUpdating = True
    Exit Sub

ErrorHandler:
    IsRefreshing = False
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic
    
    LogMessage "Error", "Refresh failed: " & Err.Description
    wsDash.Range("K3").Value = "⚠️ ERROR"
    wsDash.Range("K3").Font.Color = RGB(255, 0, 0)
End Sub

Private Sub LogMessage(statusStr As String, msg As String)
    On Error Resume Next
    Dim wsLog As Worksheet
    Set wsLog = ThisWorkbook.Sheets("Log")
    Dim lr As Long
    lr = wsLog.Cells(wsLog.Rows.Count, 1).End(xlUp).Row + 1
    
    wsLog.Cells(lr, 1).Value = Now
    wsLog.Cells(lr, 2).Value = "Auto Refresh"
    wsLog.Cells(lr, 3).Value = "System"
    wsLog.Cells(lr, 4).Value = msg
    wsLog.Cells(lr, 5).Value = statusStr
    On Error GoTo 0
End Sub

' -------------------------------------------------------------------------
' Timer Scheduling
' -------------------------------------------------------------------------
Public Sub ScheduleNextRefresh()
    Dim wsSettings As Worksheet
    On Error Resume Next
    Set wsSettings = ThisWorkbook.Sheets("Settings")
    On Error GoTo 0
    
    If Not wsSettings Is Nothing Then
        ' Check if Auto Refresh is ON
        If UCase(Trim(wsSettings.Range("B4").Value)) = "ON" Then
            RunTime = Now + TimeSerial(0, GetRefreshInterval(), 0)
            Application.OnTime RunTime, "TimerTick"
        End If
    End If
End Sub

Public Sub StopRefreshTimer()
    On Error Resume Next
    If RunTime <> 0 Then
        Application.OnTime RunTime, "TimerTick", , False
        RunTime = 0
    End If
    On Error GoTo 0
End Sub

Public Sub TimerTick()
    RefreshDashboard
    ScheduleNextRefresh
End Sub

Private Function GetRefreshInterval() As Integer
    Dim wsSettings As Worksheet
    Set wsSettings = ThisWorkbook.Sheets("Settings")
    Dim minVal As Integer
    minVal = 5
    On Error Resume Next
    minVal = CInt(wsSettings.Range("B5").Value)
    On Error GoTo 0
    If minVal <= 0 Then minVal = 5
    GetRefreshInterval = minVal
End Function
