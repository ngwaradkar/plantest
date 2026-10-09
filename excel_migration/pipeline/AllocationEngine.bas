Attribute VB_Name = "AllocationEngine"
Option Explicit

' -------------------------------------------------------------------------
' Main Entry Point for Allocation Engine
' -------------------------------------------------------------------------
Public Sub RunAllocation()
    Dim wsFloat As Worksheet, wsAlloc As Worksheet, wsBOM As Worksheet
    Dim wsStock As Worksheet, wsCockpit As Worksheet, wsWiring As Worksheet
    Dim wsCalc As Worksheet
    
    Set wsFloat = ThisWorkbook.Sheets("_RawFloat")
    Set wsAlloc = ThisWorkbook.Sheets("FIFO Allocation")
    Set wsBOM = ThisWorkbook.Sheets("BOM")
    Set wsStock = ThisWorkbook.Sheets("Stock")
    Set wsCockpit = ThisWorkbook.Sheets("Cockpit")
    Set wsWiring = ThisWorkbook.Sheets("Front Wiring")
    Set wsCalc = ThisWorkbook.Sheets("_CalcEngine")
    
    ' 1. Prepare PBS Queue
    Dim arrQueue As Variant
    arrQueue = PreparePBSQueue(wsFloat, wsCalc)
    
    If IsEmpty(arrQueue) Then
        MsgBox "No valid cabs found in float report.", vbInformation
        Exit Sub
    End If
    
    ' 2. Load Dictionaries
    Dim dictBOM As Object, dictEngine As Object, dictCockpit As Object, dictWiring As Object, dictNova As Object
    Set dictBOM = LoadBOM(wsBOM)
    Set dictEngine = LoadStock(wsStock.ListObjects("tblEngineStock"))
    Set dictNova = LoadStock(wsStock.ListObjects("tblNovaStock"))
    Set dictCockpit = LoadStock(wsCockpit.ListObjects("tblCockpit"))
    Set dictWiring = LoadStock(wsWiring.ListObjects("tblWiring"))
    
    Dim arrModelShortages As Variant
    arrModelShortages = LoadModelShortages(wsStock.ListObjects("tblModelShortage"))
    
    ' 3. Initialize Output Array
    Dim numRows As Long
    numRows = UBound(arrQueue, 1)
    Dim arrOut() As Variant
    ReDim arrOut(1 To numRows, 1 To 17)
    
    ' 4. Run FIFO Loop
    Dim i As Long
    Dim biw As String, vin As String, vc As String, svc As String
    Dim pbs As String, color As String, prod As String, sdesc As String, shop As String
    Dim engPart As String, ckPart As String, whPart As String
    Dim isEv As Boolean, isBattery As Boolean
    Dim hasEngine As Boolean, hasCockpit As Boolean, hasWiring As Boolean, hasModelShortage As Boolean
    Dim blockReason As String
    Dim bomMissing As Boolean, bomIncomplete As Boolean
    
    For i = 1 To numRows
        biw = CStr(arrQueue(i, 1))
        vin = CStr(arrQueue(i, 2))
        vc = CStr(arrQueue(i, 3))
        pbs = CStr(arrQueue(i, 4))
        color = CStr(arrQueue(i, 5))
        prod = CStr(arrQueue(i, 6))
        sdesc = CStr(arrQueue(i, 7))
        shop = CStr(arrQueue(i, 8))
        
        svc = Left(vc, 9)
        
        arrOut(i, 1) = biw
        arrOut(i, 2) = vin
        arrOut(i, 3) = vc
        arrOut(i, 4) = svc
        arrOut(i, 5) = pbs
        arrOut(i, 6) = color
        arrOut(i, 7) = prod
        arrOut(i, 8) = sdesc
        arrOut(i, 9) = shop
        
        hasEngine = True: hasCockpit = True: hasWiring = True: hasModelShortage = False
        blockReason = ""
        
        If dictBOM.Exists(svc) Then
            Dim parts As Variant
            parts = dictBOM(svc)
            engPart = parts(0)
            ckPart = parts(1)
            whPart = parts(2)
            
            arrOut(i, 12) = engPart
            arrOut(i, 13) = ckPart
            arrOut(i, 14) = whPart
            
            isEv = (InStr(1, UCase(prod), "EV") > 0 Or InStr(1, UCase(prod), "NOVA") > 0)
            isBattery = (engPart = "546816111212" Or engPart = "547380400103" Or isEv)
            
            bomIncomplete = False
            Dim incParts As String: incParts = ""
            If engPart = "" Or engPart = "0" Or engPart = "None" Then
                bomIncomplete = True
                incParts = IIf(isBattery, "Battery", "Engine")
            End If
            If ckPart = "" Or ckPart = "0" Or ckPart = "None" Then
                bomIncomplete = True
                incParts = incParts & IIf(incParts = "", "", ", ") & "Cockpit"
            End If
            If whPart = "" Or whPart = "0" Or whPart = "None" Then
                bomIncomplete = True
                incParts = incParts & IIf(incParts = "", "", ", ") & "Front Wiring"
            End If
            
            If bomIncomplete Then
                arrOut(i, 10) = "⚠️ BOM Incomplete"
                arrOut(i, 11) = "Incomplete BOM for parts: " & incParts
            Else
                ' Check Stocks
                Dim engStock As Long, ckStock As Long, whStock As Long
                
                ' ENGINE / NOVA
                If engPart = "546816111212" Then
                    Dim matShort As String
                    matShort = ""
                    Dim novaMats As Variant
                    novaMats = Array("Battery", "Combo", "Tube Frame(Craddle)", "Subframe", "RTB")
                    Dim j As Long
                    For j = 0 To UBound(novaMats)
                        Dim mName As String: mName = CStr(novaMats(j))
                        If dictNova.Exists(mName) Then
                            If dictNova(mName) <= 0 Then
                                hasEngine = False
                                matShort = matShort & IIf(matShort = "", "", ", ") & mName & " (Stock: " & dictNova(mName) & ")"
                            End If
                        Else
                            hasEngine = False
                            matShort = matShort & IIf(matShort = "", "", ", ") & mName & " (Stock: 0)"
                        End If
                    Next j
                    If Not hasEngine Then blockReason = matShort
                Else
                    If dictEngine.Exists(engPart) Then
                        engStock = dictEngine(engPart)
                        If engStock <= 0 Then
                            hasEngine = False
                            blockReason = IIf(isBattery, "Battery ", "Engine ") & engPart & " (Stock: " & engStock & ")"
                        End If
                    Else
                        hasEngine = False
                        blockReason = IIf(isBattery, "Battery ", "Engine ") & engPart & " (Stock: 0)"
                    End If
                End If
                
                ' COCKPIT
                If dictCockpit.Exists(ckPart) Then
                    ckStock = dictCockpit(ckPart)
                    If ckStock <= 0 Then
                        hasCockpit = False
                        blockReason = blockReason & IIf(blockReason = "", "", ", ") & "Cockpit " & ckPart & " (Stock: " & ckStock & ")"
                    End If
                Else
                    hasCockpit = False
                    blockReason = blockReason & IIf(blockReason = "", "", ", ") & "Cockpit " & ckPart & " (Stock: 0)"
                End If
                
                ' WIRING
                If dictWiring.Exists(whPart) Then
                    whStock = dictWiring(whPart)
                    If whStock <= 0 Then
                        hasWiring = False
                        blockReason = blockReason & IIf(blockReason = "", "", ", ") & "Wiring " & whPart & " (Stock: " & whStock & ")"
                    End If
                Else
                    hasWiring = False
                    blockReason = blockReason & IIf(blockReason = "", "", ", ") & "Wiring " & whPart & " (Stock: 0)"
                End If
                
                ' MODEL SHORTAGES
                Dim matchedMsIndices As Object
                Set matchedMsIndices = CreateObject("Scripting.Dictionary")
                
                If Not IsEmpty(arrModelShortages) Then
                    Dim msIdx As Long
                    For msIdx = 1 To UBound(arrModelShortages, 1)
                        Dim mMod As String, mTrm As String, mPart As String, mStk As Long
                        mMod = CStr(arrModelShortages(msIdx, 1))
                        mTrm = CStr(arrModelShortages(msIdx, 2))
                        mPart = CStr(arrModelShortages(msIdx, 3))
                        mStk = CLng(arrModelShortages(msIdx, 4))
                        
                        If IsModelTrimMatched(prod, sdesc, mMod, mTrm) Then
                            matchedMsIndices(msIdx) = True
                            If mStk <= 0 Then
                                hasModelShortage = True
                                blockReason = blockReason & IIf(blockReason = "", "", ", ") & mPart & " (Stock: " & mStk & ")"
                            End If
                        End If
                    Next msIdx
                End If
                
                ' Allocate or Block
                If hasEngine And hasCockpit And hasWiring And Not hasModelShortage Then
                    arrOut(i, 10) = "✅ Ready for TCF"
                    
                    If engPart = "546816111212" Then
                        For j = 0 To UBound(novaMats)
                            mName = CStr(novaMats(j))
                            If dictNova.Exists(mName) Then dictNova(mName) = dictNova(mName) - 1
                        Next j
                    Else
                        If dictEngine.Exists(engPart) Then dictEngine(engPart) = dictEngine(engPart) - 1
                    End If
                    
                    If dictCockpit.Exists(ckPart) Then dictCockpit(ckPart) = dictCockpit(ckPart) - 1
                    If dictWiring.Exists(whPart) Then dictWiring(whPart) = dictWiring(whPart) - 1
                    
                    Dim keyMs As Variant
                    For Each keyMs In matchedMsIndices.Keys()
                        arrModelShortages(keyMs, 4) = arrModelShortages(keyMs, 4) - 1
                    Next keyMs
                Else
                    arrOut(i, 10) = "🚫 Blocked"
                    arrOut(i, 11) = "Shortage: " & blockReason
                End If
                
                If engPart = "546816111212" Then
                    If dictNova.Exists("Battery") Then arrOut(i, 15) = dictNova("Battery")
                Else
                    If dictEngine.Exists(engPart) Then arrOut(i, 15) = dictEngine(engPart)
                End If
                If dictCockpit.Exists(ckPart) Then arrOut(i, 16) = dictCockpit(ckPart)
                If dictWiring.Exists(whPart) Then arrOut(i, 17) = dictWiring(whPart)
                
            End If
        Else
            arrOut(i, 10) = "⚠️ Unknown VC"
            arrOut(i, 11) = "VC prefix '" & svc & "' not found in BOM."
        End If
    Next i
    
    WriteOutputToTable wsAlloc.ListObjects("tblAllocation"), arrOut
    
    Dim wsLog As Worksheet
    Set wsLog = ThisWorkbook.Sheets("Log")
    Dim lr As Long
    lr = wsLog.Cells(wsLog.Rows.Count, 1).End(xlUp).Row + 1
    wsLog.Cells(lr, 1).Value = Now
    wsLog.Cells(lr, 2).Value = "VBA Allocation Engine"
    wsLog.Cells(lr, 3).Value = "System"
    wsLog.Cells(lr, 4).Value = "Successfully ran VBA FIFO allocation on " & numRows & " cabs."
    wsLog.Cells(lr, 5).Value = "✅"
    
End Sub

' -------------------------------------------------------------------------
' Helpers
' -------------------------------------------------------------------------
Private Function PreparePBSQueue(wsRaw As Worksheet, wsCalc As Worksheet) As Variant
    wsCalc.Cells.Clear
    Dim lastRow As Long
    lastRow = wsRaw.Cells(wsRaw.Rows.Count, 1).End(xlUp).Row
    If lastRow < 2 Then
        PreparePBSQueue = Empty
        Exit Function
    End If
    
    wsRaw.Range("A1").CurrentRegion.Copy wsCalc.Range("A1")
    
    Dim cBiw As Long, cVin As Long, cVc As Long, cPbs As Long, cColor As Long
    Dim cProd As Long, cDesc As Long, cShop As Long, cHolds As Long
    Dim cTopcoat As Long, cSealant As Long, cPtced As Long, cBiwLift As Long
    
    cBiw = FindColumn(wsCalc, "BIW NUMBER")
    cVin = FindColumn(wsCalc, "VIN")
    cVc = FindColumn(wsCalc, "VEHICLE CODE")
    If cVc = 0 Then cVc = FindColumn(wsCalc, "VC")
    cPbs = FindColumn(wsCalc, "PBS LIFT")
    cColor = FindColumn(wsCalc, "COLOUR")
    cProd = FindColumn(wsCalc, "PRODUCT")
    cDesc = FindColumn(wsCalc, "SALES DESCRIPTION")
    cShop = FindColumn(wsCalc, "SHOP")
    cHolds = FindColumn(wsCalc, "HOLD BY")
    
    cTopcoat = FindColumn(wsCalc, "TOPCOAT")
    cSealant = FindColumn(wsCalc, "SEALANT")
    cPtced = FindColumn(wsCalc, "PTCED")
    cBiwLift = FindColumn(wsCalc, "BIW LIFTING")
    
    Dim i As Long, rOut As Long
    Dim arrSrc As Variant
    arrSrc = wsCalc.Range("A2").Resize(lastRow - 1, wsCalc.Cells(1, wsCalc.Columns.Count).End(xlToLeft).Column).Value
    
    Dim arrFilt() As Variant
    ReDim arrFilt(1 To UBound(arrSrc, 1), 1 To 13)
    
    rOut = 0
    For i = 1 To UBound(arrSrc, 1)
        Dim hold As String
        If cHolds > 0 Then hold = CStr(arrSrc(i, cHolds)) Else hold = ""
        
        If Trim(hold) = "" Or UCase(Trim(hold)) = "NONE" Then
            rOut = rOut + 1
            arrFilt(rOut, 1) = arrSrc(i, cBiw)
            If cVin > 0 Then arrFilt(rOut, 2) = arrSrc(i, cVin)
            If cVc > 0 Then arrFilt(rOut, 3) = arrSrc(i, cVc)
            If cPbs > 0 Then arrFilt(rOut, 4) = arrSrc(i, cPbs)
            If cColor > 0 Then arrFilt(rOut, 5) = arrSrc(i, cColor)
            If cProd > 0 Then arrFilt(rOut, 6) = arrSrc(i, cProd)
            If cDesc > 0 Then arrFilt(rOut, 7) = arrSrc(i, cDesc)
            If cShop > 0 Then arrFilt(rOut, 8) = arrSrc(i, cShop)
            
            If cPbs > 0 And Not IsEmpty(arrSrc(i, cPbs)) Then arrFilt(rOut, 9) = CDbl(arrSrc(i, cPbs)) Else arrFilt(rOut, 9) = 99999
            If cTopcoat > 0 And Not IsEmpty(arrSrc(i, cTopcoat)) Then arrFilt(rOut, 10) = CDbl(arrSrc(i, cTopcoat)) Else arrFilt(rOut, 10) = 99999
            If cSealant > 0 And Not IsEmpty(arrSrc(i, cSealant)) Then arrFilt(rOut, 11) = CDbl(arrSrc(i, cSealant)) Else arrFilt(rOut, 11) = 99999
            If cPtced > 0 And Not IsEmpty(arrSrc(i, cPtced)) Then arrFilt(rOut, 12) = CDbl(arrSrc(i, cPtced)) Else arrFilt(rOut, 12) = 99999
            If cBiwLift > 0 And Not IsEmpty(arrSrc(i, cBiwLift)) Then arrFilt(rOut, 13) = CDbl(arrSrc(i, cBiwLift)) Else arrFilt(rOut, 13) = 99999
        End If
    Next i
    
    If rOut = 0 Then
        PreparePBSQueue = Empty
        Exit Function
    End If
    
    wsCalc.Cells.Clear
    wsCalc.Range("A1").Resize(rOut, 13).Value = arrFilt
    
    wsCalc.Sort.SortFields.Clear
    wsCalc.Sort.SortFields.Add Key:=wsCalc.Columns(9), SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
    wsCalc.Sort.SortFields.Add Key:=wsCalc.Columns(10), SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
    wsCalc.Sort.SortFields.Add Key:=wsCalc.Columns(11), SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
    wsCalc.Sort.SortFields.Add Key:=wsCalc.Columns(12), SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
    wsCalc.Sort.SortFields.Add Key:=wsCalc.Columns(13), SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
    
    With wsCalc.Sort
        .SetRange wsCalc.Range("A1:M" & rOut)
        .Header = xlNo
        .MatchCase = False
        .Orientation = xlTopToBottom
        .SortMethod = xlPinYin
        .Apply
    End With
    
    PreparePBSQueue = wsCalc.Range("A1:H" & rOut).Value
End Function

Private Function FindColumn(ws As Worksheet, colName As String) As Long
    Dim fnd As Range
    Set fnd = ws.Rows(1).Find(What:=colName, LookIn:=xlValues, LookAt:=xlWhole, MatchCase:=False)
    If Not fnd Is Nothing Then
        FindColumn = fnd.Column
    Else
        FindColumn = 0
    End If
End Function

Private Function LoadBOM(ws As Worksheet) As Object
    Dim dict As Object
    Set dict = CreateObject("Scripting.Dictionary")
    dict.CompareMode = vbTextCompare
    
    Dim tbl As ListObject
    Set tbl = ws.ListObjects("tblBOM")
    If tbl.DataBodyRange Is Nothing Then
        Set LoadBOM = dict
        Exit Function
    End If
    
    Dim arr As Variant
    arr = tbl.DataBodyRange.Value
    
    Dim cSvc As Long, cEng As Long, cCk As Long, cWh As Long
    cSvc = tbl.ListColumns("Short Vehicle Code").Index
    cEng = tbl.ListColumns("Engine").Index
    cCk = tbl.ListColumns("Cockpit").Index
    cWh = tbl.ListColumns("Front Wiring").Index
    
    Dim i As Long
    For i = 1 To UBound(arr, 1)
        Dim svc As String: svc = Trim(CStr(arr(i, cSvc)))
        If svc <> "" Then
            dict(svc) = Array(Trim(CStr(arr(i, cEng))), Trim(CStr(arr(i, cCk))), Trim(CStr(arr(i, cWh))))
        End If
    Next i
    
    Set LoadBOM = dict
End Function

Private Function LoadStock(tbl As ListObject) As Object
    Dim dict As Object
    Set dict = CreateObject("Scripting.Dictionary")
    dict.CompareMode = vbTextCompare
    
    If tbl.DataBodyRange Is Nothing Then
        Set LoadStock = dict
        Exit Function
    End If
    
    Dim arr As Variant
    arr = tbl.DataBodyRange.Value
    
    Dim colPart As String
    If tbl.Name = "tblNovaStock" Then colPart = "Material" Else colPart = "Part Number"
    
    Dim cPart As Long, cStock As Long
    On Error Resume Next
    cPart = tbl.ListColumns(colPart).Index
    cStock = tbl.ListColumns("True Current Stock").Index
    On Error GoTo 0
    
    Dim i As Long
    For i = 1 To UBound(arr, 1)
        Dim part As String: part = Trim(CStr(arr(i, cPart)))
        If part <> "" Then
            Dim val As Variant: val = arr(i, cStock)
            Dim qty As Long
            If IsNumeric(val) Then qty = CLng(val) Else qty = 0
            dict(part) = qty
        End If
    Next i
    
    Set LoadStock = dict
End Function

Private Function LoadModelShortages(tbl As ListObject) As Variant
    If tbl.DataBodyRange Is Nothing Then
        LoadModelShortages = Empty
        Exit Function
    End If
    
    Dim arr As Variant
    arr = tbl.DataBodyRange.Value
    
    Dim cMod As Long, cTrm As Long, cPart As Long, cStk As Long
    On Error Resume Next
    cMod = tbl.ListColumns("Model").Index
    cTrm = tbl.ListColumns("Trims").Index
    cPart = tbl.ListColumns("Part Name").Index
    cStk = tbl.ListColumns("True Current Stock").Index
    On Error GoTo 0
    
    If cMod = 0 Then
        LoadModelShortages = Empty
        Exit Function
    End If
    
    Dim arrOut() As Variant
    ReDim arrOut(1 To UBound(arr, 1), 1 To 4)
    
    Dim i As Long
    For i = 1 To UBound(arr, 1)
        arrOut(i, 1) = CStr(arr(i, cMod))
        arrOut(i, 2) = CStr(arr(i, cTrm))
        arrOut(i, 3) = CStr(arr(i, cPart))
        If IsNumeric(arr(i, cStk)) Then arrOut(i, 4) = CLng(arr(i, cStk)) Else arrOut(i, 4) = 0
    Next i
    
    LoadModelShortages = arrOut
End Function

Private Function IsModelTrimMatched(cabModel As String, cabSalesDesc As String, targetModel As String, targetTrims As String) As Boolean
    Dim tMod As String, cMod As String, cDesc As String
    tMod = Trim(UCase(targetModel))
    cMod = Trim(UCase(cabModel))
    cDesc = Trim(UCase(cabSalesDesc))
    
    Dim modelMatch As Boolean
    modelMatch = False
    
    If tMod = "HARRIER / SAFARI" Then
        If InStr(cMod, "HARRIER") > 0 Or InStr(cDesc, "HARRIER") > 0 Or _
           InStr(cMod, "SAFARI") > 0 Or InStr(cDesc, "SAFARI") > 0 Or _
           InStr(cMod, "GRAVITAS") > 0 Or InStr(cDesc, "GRAVITAS") > 0 Or _
           InStr(cMod, "Q5") > 0 Or InStr(cDesc, "Q5") > 0 Then
            modelMatch = True
        End If
    ElseIf tMod = "HARRIER.EV" Then
        If InStr(cMod, "HARRIER.EV") > 0 Or InStr(cDesc, "HARRIER.EV") > 0 Or _
           InStr(cMod, "ETURNA") > 0 Or InStr(cDesc, "ETURNA") > 0 Then
            modelMatch = True
        End If
    ElseIf tMod = "PUNCH.EV" Then
        If InStr(cMod, "PUNCH.EV") > 0 Or InStr(cDesc, "PUNCH.EV") > 0 Or _
           InStr(cMod, "NOVA") > 0 Or InStr(cDesc, "NOVA") > 0 Then
            modelMatch = True
        End If
    ElseIf tMod = "PUNCH" Then
        If (InStr(cMod, "PUNCH") > 0 Or InStr(cDesc, "PUNCH") > 0 Or InStr(cMod, "HORNBILL") > 0 Or InStr(cDesc, "HORNBILL") > 0) And _
           InStr(cMod, "EV") = 0 And InStr(cMod, "NOVA") = 0 And InStr(cDesc, "PUNCH.EV") = 0 Then
            modelMatch = True
        End If
    Else
        If InStr(cMod, tMod) > 0 Or InStr(cDesc, tMod) > 0 Then
            modelMatch = True
        End If
    End If
    
    If Not modelMatch Then
        IsModelTrimMatched = False
        Exit Function
    End If
    
    Dim tTrims As String
    tTrims = Trim(UCase(targetTrims))
    If tTrims = "" Or InStr(tTrims, "ALL TRIMS") > 0 Then
        IsModelTrimMatched = True
        Exit Function
    End If
    
    Dim arrTrims As Variant
    arrTrims = Split(tTrims, ",")
    Dim i As Long
    For i = 0 To UBound(arrTrims)
        If InStr(cDesc, Trim(arrTrims(i))) > 0 Then
            IsModelTrimMatched = True
            Exit Function
        End If
    Next i
    
    IsModelTrimMatched = False
End Function

Private Sub WriteOutputToTable(tbl As ListObject, arr As Variant)
    If Not tbl.DataBodyRange Is Nothing Then
        tbl.DataBodyRange.Delete
    End If
    
    Dim numRows As Long, numCols As Long
    numRows = UBound(arr, 1)
    numCols = UBound(arr, 2)
    
    tbl.Parent.Range("A3").Resize(numRows, numCols).Value = arr
    tbl.Resize tbl.Range.Resize(numRows + 1, tbl.Range.Columns.Count)
End Sub
