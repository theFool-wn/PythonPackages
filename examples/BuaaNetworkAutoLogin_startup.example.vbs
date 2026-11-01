' Copy this file and BuaaNetworkAutoLogin.json to the same private directory.
' Edit PythonExe to the python.exe where buaa-network-autologin is installed.
' A shortcut to this VBS can be put in shell:startup.
' Log location is set by the package default or log_path in the private JSON.
Dim WshShell, Fso, ScriptDir, PythonExe, Config, Command
Set WshShell = CreateObject("WScript.Shell")
Set Fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = Fso.GetParentFolderName(WScript.ScriptFullName)
PythonExe = "C:\path\to\venv\Scripts\python.exe"
Config = Fso.BuildPath(ScriptDir, "BuaaNetworkAutoLogin.json")
Command = Chr(34) & PythonExe & Chr(34) & " -m BuaaNetworkAutoLogin watch --config " & Chr(34) & Config & Chr(34)
WshShell.Run Command, 0, False
