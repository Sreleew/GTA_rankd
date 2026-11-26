Option Explicit
Dim fso, shell, projectRoot, pythonw, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = projectRoot & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(pythonw) Then
    MsgBox "GTA Ranked Studio n'est pas installe. Lance INSTALL.bat dans le dossier du projet.", vbExclamation, "GTA Ranked Studio"
    WScript.Quit 1
End If

shell.CurrentDirectory = projectRoot
command = Chr(34) & pythonw & Chr(34) & " -m studio.desktop_launcher"
shell.Run command, 0, False
